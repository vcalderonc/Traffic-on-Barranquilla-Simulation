variable "region" {
  description = "Región de AWS (us-east-1 suele tener el spot más barato)."
  type        = string
  default     = "us-east-1"
}

variable "lanzar" {
  description = "true = crea la instancia spot y entrena. false = solo deja el bucket (para bajar resultados sin pagar cómputo)."
  type        = bool
  default     = true
}

variable "tipo_instancia" {
  description = "Tipo de instancia. Solo CPU: SUMO y el DQN usan un núcleo por proceso, así que importan los vCPU."
  type        = string
  default     = "c7a.8xlarge" # 32 vCPU AMD
}

variable "precio_maximo" {
  description = "Precio máximo por hora del spot en USD. null = hasta el precio on-demand."
  type        = string
  default     = null
}

variable "horas_maximas" {
  description = "Seguro de costos: la instancia se apaga (y termina) después de estas horas pase lo que pase."
  type        = number
  default     = 3
}

variable "disco_gb" {
  description = "Tamaño del disco raíz (gp3)."
  type        = number
  default     = 30
}

variable "repo" {
  description = "Repositorio a clonar en la instancia."
  type        = string
  default     = "https://github.com/vcalderonc/Traffic-on-Barranquilla-Simulation.git"
}

variable "rama" {
  description = "Rama del repositorio con el código de entrenamiento."
  type        = string
  default     = "main"
}

variable "corrida" {
  description = "Nombre de la corrida: prefijo en S3 (s3://<bucket>/<corrida>/...). Cámbialo en cada entrenamiento."
  type        = string
  default     = "fase2-spot-1"
}

variable "semillas" {
  description = "Semillas en paralelo (una por núcleo). null = vCPU - 1."
  type        = number
  default     = null
}

variable "semilla_inicial" {
  description = "Primera semilla. Empieza en 101 para no pisar los candidatos s1..s6 que ya están en el repo."
  type        = number
  default     = 101
}

variable "episodios" {
  description = "Episodios de entrenamiento por semilla."
  type        = number
  default     = 600
}

variable "evaluar_cada" {
  description = "Episodios entre evaluaciones (se guarda el mejor punto de control)."
  type        = number
  default     = 50
}

variable "episodios_validacion" {
  description = "Episodios de validación por candidato (mismo mundo para todos)."
  type        = number
  default     = 40
}

variable "ssh_cidr" {
  description = "CIDR con acceso SSH (p. ej. \"1.2.3.4/32\"). null = sin SSH; se entra con SSM Session Manager."
  type        = string
  default     = null
}

variable "llave_ssh" {
  description = "Nombre de un par de llaves de EC2 existente (solo si se usa ssh_cidr)."
  type        = string
  default     = null
}

variable "borrar_bucket_con_datos" {
  description = "true = terraform destroy borra el bucket aunque tenga resultados."
  type        = bool
  default     = false
}

variable "zona" {
  description = "Zona de disponibilidad (p. ej. \"us-east-1c\", donde el spot esté más barato). null = la primera con el tipo de instancia."
  type        = string
  default     = null
}
