# Entrenamiento de la Fase 2 en una instancia spot (ver docs/EC2.md).
#
# La instancia arranca, clona el repo, entrena, valida y sube todo a S3; al terminar (o al
# fallar, o al cumplir var.horas_maximas) se apaga, y como es spot de una sola vez, se termina.
# El bucket se queda con los resultados.

# ------------------------------------------------------------------ resultados
resource "aws_s3_bucket" "resultados" {
  bucket_prefix = "bq-sim-entrenamiento-"
  force_destroy = var.borrar_bucket_con_datos
}

resource "aws_s3_bucket_public_access_block" "resultados" {
  bucket                  = aws_s3_bucket.resultados.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "resultados" {
  bucket = aws_s3_bucket.resultados.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "resultados" {
  bucket = aws_s3_bucket.resultados.id
  versioning_configuration {
    status = "Enabled" # un sync tardío no puede pisar sin remedio un buen punto de control
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "resultados" {
  bucket = aws_s3_bucket.resultados.id
  rule {
    id     = "versiones-viejas"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 2
    }
  }
}

# ------------------------------------------------------------------ permisos de la instancia
data "aws_iam_policy_document" "asumir_ec2" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "entrenador" {
  name_prefix        = "bq-sim-entrenador-"
  assume_role_policy = data.aws_iam_policy_document.asumir_ec2.json
}

data "aws_iam_policy_document" "s3_resultados" {
  statement {
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.resultados.arn]
  }
  statement {
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.resultados.arn}/*"]
  }
}

resource "aws_iam_role_policy" "s3_resultados" {
  name   = "s3-resultados"
  role   = aws_iam_role.entrenador.id
  policy = data.aws_iam_policy_document.s3_resultados.json
}

# entrar sin SSH ni puertos abiertos: aws ssm start-session --target <id>
resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.entrenador.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "entrenador" {
  name_prefix = "bq-sim-entrenador-"
  role        = aws_iam_role.entrenador.name
}

# ------------------------------------------------------------------ red
# VPC propia y mínima: subredes públicas con internet gateway (sin NAT, que cobra por hora).
# La instancia no acepta conexiones entrantes salvo SSH opcional (ver aws_security_group).
resource "aws_vpc" "entrenamiento" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "bq-sim-entrenamiento" }
}

resource "aws_internet_gateway" "entrenamiento" {
  vpc_id = aws_vpc.entrenamiento.id
  tags   = { Name = "bq-sim-entrenamiento" }
}

# zonas donde existe el tipo de instancia (no todas las AZ tienen todos los tipos)
data "aws_ec2_instance_type_offerings" "zonas" {
  location_type = "availability-zone"
  filter {
    name   = "instance-type"
    values = [var.tipo_instancia]
  }
}

locals {
  zonas = slice(sort(data.aws_ec2_instance_type_offerings.zonas.locations), 0,
  min(3, length(data.aws_ec2_instance_type_offerings.zonas.locations)))
}

resource "aws_subnet" "publica" {
  for_each                = { for i, z in local.zonas : z => i }
  vpc_id                  = aws_vpc.entrenamiento.id
  availability_zone       = each.key
  cidr_block              = cidrsubnet(aws_vpc.entrenamiento.cidr_block, 8, each.value)
  map_public_ip_on_launch = true
  tags                    = { Name = "bq-sim-${each.key}" }
}

resource "aws_route_table" "publica" {
  vpc_id = aws_vpc.entrenamiento.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.entrenamiento.id
  }
  tags = { Name = "bq-sim-entrenamiento" }
}

resource "aws_route_table_association" "publica" {
  for_each       = aws_subnet.publica
  subnet_id      = each.value.id
  route_table_id = aws_route_table.publica.id
}

# S3 por el endpoint de la VPC: gratis y sin salir a internet
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.entrenamiento.id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.publica.id]
}

locals {
  # se puede elegir la zona con el spot más barato: -var zona=us-east-1c
  subred = var.zona == null ? aws_subnet.publica[local.zonas[0]].id : aws_subnet.publica[var.zona].id
}

resource "aws_security_group" "entrenador" {
  name_prefix = "bq-sim-entrenador-"
  description = "Entrenamiento bq-sim: sin entrada salvo SSH opcional; salida libre (pip, git, S3)."
  vpc_id      = aws_vpc.entrenamiento.id

  dynamic "ingress" {
    for_each = var.ssh_cidr == null ? [] : [var.ssh_cidr]
    content {
      description = "SSH"
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = [ingress.value]
    }
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ------------------------------------------------------------------ instancia spot
data "aws_ec2_instance_type" "tipo" {
  instance_type = var.tipo_instancia
}

locals {
  arquitectura = contains(data.aws_ec2_instance_type.tipo.supported_architectures, "arm64") ? "arm64" : "amd64"
  vcpus        = data.aws_ec2_instance_type.tipo.default_vcpus
  semillas     = coalesce(var.semillas, max(1, local.vcpus - 1))
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-${local.arquitectura}-server-*"]
  }
}

resource "aws_instance" "entrenador" {
  count = var.lanzar ? 1 : 0

  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.tipo_instancia
  subnet_id              = local.subred
  vpc_security_group_ids = [aws_security_group.entrenador.id]
  iam_instance_profile   = aws_iam_instance_profile.entrenador.name
  key_name               = var.llave_ssh

  instance_market_options {
    market_type = "spot"
    spot_options {
      spot_instance_type             = "one-time"
      instance_interruption_behavior = "terminate"
      max_price                      = var.precio_maximo
    }
  }
  instance_initiated_shutdown_behavior = "terminate"

  metadata_options {
    http_tokens   = "required" # IMDSv2
    http_endpoint = "enabled"
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.disco_gb
    encrypted             = true
    delete_on_termination = true
  }

  user_data_replace_on_change = true
  user_data = templatefile("${path.module}/arranque.sh.tftpl", {
    repo            = var.repo
    rama            = var.rama
    bucket          = "s3://${aws_s3_bucket.resultados.bucket}/${var.corrida}"
    semillas        = local.semillas
    semilla_inicial = var.semilla_inicial
    episodios       = var.episodios
    evaluar_cada    = var.evaluar_cada
    validar         = var.episodios_validacion
    minutos_maximos = floor(var.horas_maximas * 60)
  })

  tags = {
    Name    = "bq-sim-${var.corrida}"
    Corrida = var.corrida
  }

  depends_on = [aws_iam_role_policy.s3_resultados, aws_route_table_association.publica]
}
