# Dashboard de CloudWatch: la instancia (CPU, red, memoria) y el avance del entrenamiento
# por grupo de ajuste (D-37), publicado por scripts/ec2/metricas.py cada minuto.

locals {
  ns      = "BQSim/Entrenamiento"
  id_inst = try(aws_instance.entrenador[0].id, "ninguna")

  # una serie por grupo de ajuste (delta, lr) de esta corrida
  por_grupo = { for m in ["Episodios", "Atropellos10", "Choques10", "VelocidadKmh", "EvalAtropellos", "EvalVelocidadKmh", "SemillasVivas", "SemillasConError"] :
    m => [[{ expression = "SEARCH('{${local.ns},Corrida,Grupo} MetricName=\"${m}\" Corrida=\"${var.corrida}\"', 'Average', 60)", id = "e1", label = "" }]]
  }

  grafica = { for nombre, cfg in {
    episodios  = { t = "Episodios por semilla (de ${var.episodios})", m = "Episodios", x = 0, y = 6 }
    atropellos = { t = "Atropellos en los últimos 10 episodios (entrenamiento)", m = "Atropellos10", x = 8, y = 6 }
    velocidad  = { t = "Velocidad media (km/h, entrenamiento)", m = "VelocidadKmh", x = 16, y = 6 }
    eval_atr   = { t = "Atropellos en la última evaluación (sin exploración)", m = "EvalAtropellos", x = 0, y = 12 }
    eval_vel   = { t = "Velocidad en la última evaluación (km/h)", m = "EvalVelocidadKmh", x = 8, y = 12 }
    choques    = { t = "Choques en los últimos 10 episodios", m = "Choques10", x = 16, y = 12 }
    } : nombre => {
    type   = "metric"
    x      = cfg.x
    y      = cfg.y
    width  = 8
    height = 6
    properties = {
      title   = cfg.t
      region  = var.region
      view    = "timeSeries"
      stat    = "Average"
      period  = 60
      metrics = local.por_grupo[cfg.m]
      legend  = { position = "bottom" }
    }
  } }
}

resource "aws_cloudwatch_dashboard" "entrenamiento" {
  dashboard_name = "bq-sim-entrenamiento"
  dashboard_body = jsonencode({
    widgets = concat([
      {
        type   = "text"
        x      = 0
        y      = 0
        width  = 24
        height = 2
        properties = {
          markdown = "## Entrenamiento Fase 2 · corrida `${var.corrida}`\n${var.tipo_instancia} spot (`${local.id_inst}`) · ${local.semillas} semillas x ${var.episodios} episodios · grupos (delta Huber, lr): ${join(", ", var.ajustes)} · se termina sola a las ${var.horas_maximas} h · resultados en `s3://${aws_s3_bucket.resultados.bucket}/${var.corrida}/`"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 2
        width  = 8
        height = 4
        properties = {
          title   = "CPU de la instancia (%)"
          region  = var.region
          view    = "timeSeries"
          stat    = "Average"
          period  = 60
          yAxis   = { left = { min = 0, max = 100 } }
          metrics = [["AWS/EC2", "CPUUtilization", "InstanceId", local.id_inst]]
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 2
        width  = 8
        height = 4
        properties = {
          title   = "Memoria usada (%)"
          region  = var.region
          view    = "timeSeries"
          stat    = "Average"
          period  = 60
          yAxis   = { left = { min = 0, max = 100 } }
          metrics = [[local.ns, "MemoriaUsadaPct", "Corrida", var.corrida]]
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 2
        width  = 8
        height = 4
        properties = {
          title   = "Semillas vivas / con error"
          region  = var.region
          view    = "singleValue"
          stat    = "Maximum"
          period  = 60
          metrics = concat(local.por_grupo["SemillasVivas"], [[{ expression = "SEARCH('{${local.ns},Corrida,Grupo} MetricName=\"SemillasConError\" Corrida=\"${var.corrida}\"', 'Maximum', 60)", id = "e2", label = "con error" }]])
        }
      },
    ], values(local.grafica))
  })
}

output "dashboard" {
  description = "Dashboard de CloudWatch con la instancia y el avance del entrenamiento."
  value       = "https://${var.region}.console.aws.amazon.com/cloudwatch/home?region=${var.region}#dashboards/dashboard/${aws_cloudwatch_dashboard.entrenamiento.dashboard_name}"
}
