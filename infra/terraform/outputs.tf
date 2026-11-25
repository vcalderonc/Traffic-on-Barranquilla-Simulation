output "bucket" {
  description = "Bucket con los resultados."
  value       = aws_s3_bucket.resultados.bucket
}

output "instancia" {
  description = "ID de la instancia spot (null si lanzar = false)."
  value       = try(aws_instance.entrenador[0].id, null)
}

output "resumen" {
  description = "Qué se lanzó."
  value = var.lanzar ? format("%s spot · %d semillas (%d..%d) x %d episodios · máximo %s h",
    var.tipo_instancia, local.semillas, var.semilla_inicial, var.semilla_inicial + local.semillas - 1,
  var.episodios, var.horas_maximas) : "sin instancia"
}

output "comandos" {
  description = "Cómo seguir el entrenamiento y traer los resultados."
  value       = <<-EOT
    # entrar a la instancia (sin SSH; requiere el plugin de Session Manager)
    aws ssm start-session --region ${var.region} --target ${try(aws_instance.entrenador[0].id, "<sin instancia>")}
    #   sudo tail -f /var/log/entrenamiento.log
    #   tail -f ~ubuntu/Traffic-on-Barranquilla-Simulation/salidas/fase2/log_s${var.semilla_inicial}.txt

    # ¿sigue viva?
    aws ec2 describe-instances --region ${var.region} --instance-ids ${try(aws_instance.entrenador[0].id, "<sin instancia>")} --query 'Reservations[].Instances[].State.Name' --output text

    # traer resultados (desde la raíz del repo)
    aws s3 sync s3://${aws_s3_bucket.resultados.bucket}/${var.corrida}/modelos/fase2 modelos/fase2
    aws s3 sync s3://${aws_s3_bucket.resultados.bucket}/${var.corrida}/salidas/fase2 salidas/fase2
    aws s3 cp   s3://${aws_s3_bucket.resultados.bucket}/${var.corrida}/modelos/instructor_automovil.npz modelos/instructor_automovil.npz
  EOT
}
