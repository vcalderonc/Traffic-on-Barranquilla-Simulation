# Entrenar en una instancia EC2

El simulador (SUMO/libsumo) y el DQN (NumPy) usan **solo CPU**, un núcleo por proceso.
Una GPU no acelera nada; lo que sirve es tener **muchos núcleos** para correr varias
semillas a la vez.

## Cuánto tarda

Medido en un Mac de 8 núcleos: ~2.7 s por episodio, así que una semilla de la Fase 2
(300 episodios + 7 evaluaciones de 8 episodios) toma unos **16 minutos**.

| Trabajo | Local (8 núcleos) | c7i.4xlarge (16 vCPU) | c7i.8xlarge (32 vCPU) |
|---|---|---|---|
| Fase 2, 6 semillas x 300 ep. | ~20 min | ~20 min | ~20 min |
| Fase 2, 15 / 31 semillas x 600 ep. | 2–3 h | ~35 min (15) | ~35 min (31) |
| Validación, 40 ep. por candidato | ~2 min c/u | ~2 min c/u | ~2 min c/u |

Con pocas semillas, el equipo local basta. El EC2 vale la pena para barridos grandes
(muchas semillas o hiperparámetros) y para reentrenar la flota (E2–E7) con la
observación nueva sin ocupar el equipo.

## Instancia recomendada

* **Tipo:** `c7i.4xlarge` (16 vCPU) para empezar; `c7i.8xlarge` (32 vCPU) para barridos.
  También sirven `c7a` (AMD) o `c6i`. La memoria no es problema (~1 GB por proceso).
* **Compra:** *Spot*. Es mucho más barata y el script sube los resultados a S3 cada
  10 minutos, así que una interrupción solo pierde lo último.
* **Región:** `us-east-1` suele ser más barata que `sa-east-1` (São Paulo). La latencia no
  importa porque el entrenamiento corre solo.
* **Imagen:** Ubuntu Server 24.04 LTS, 30 GB de disco gp3.
* **Seguridad:** grupo de seguridad con SSH (22) abierto **solo a tu IP**; un par de llaves propio.
* Revisa el precio actual por hora en la consola de AWS antes de lanzar, y **apaga** la
  instancia al terminar (`APAGAR=1` lo hace solo).

## Con Terraform (recomendado)

`infra/terraform/` crea todo y entrena sin entrar a la instancia:

* un bucket S3 privado (cifrado, con versiones) para los resultados;
* una VPC mínima (subredes públicas, sin NAT) con endpoint gratuito a S3;
* un rol de IAM que solo puede leer y escribir en ese bucket, más Session Manager para
  entrar sin SSH ni puertos abiertos;
* una instancia **spot** de una sola vez (`c7a.8xlarge`, 32 vCPU, Ubuntu 24.04) que al
  arrancar clona el repo, corre `preparar.sh` y `entrenar_fase2.sh` (31 semillas,
  101–131, x 600 episodios), valida en paralelo, instala el mejor y sube todo a S3.

Al terminar, si algo falla o si pasan `horas_maximas` (3 por defecto), la instancia se
apaga y, por ser spot, **se termina sola**: no queda cobrando. Si AWS la interrumpe, el
script ve el aviso (unos 2 minutos antes) y sube lo que tenga; además sube cada 10 minutos.

```bash
cd infra/terraform
terraform init
terraform plan                       # revisar qué se crea
terraform apply                      # crea el bucket y lanza el entrenamiento
terraform output comandos            # cómo seguirlo y traer los resultados

# otra corrida (nuevo prefijo en S3, otro rango de semillas):
terraform apply -var corrida=fase2-spot-2 -var semilla_inicial=201
# solo bajar resultados, sin instancia:
terraform apply -var lanzar=false
# borrar todo (el bucket solo se borra si está vacío, o con -var borrar_bucket_con_datos=true)
terraform destroy
```

Variables útiles: `tipo_instancia`, `zona` (la AZ con el spot más barato), `semillas`,
`episodios`, `horas_maximas`, `precio_maximo`, `rama` (la rama que se clona: tiene que
estar en GitHub). Ver `variables.tf`.

Costo de referencia (us-east-1, nov. 2026): `c7a.8xlarge` spot ~0.54 USD/h; una corrida
de 31 x 600 episodios tarda ~1 h, así que cuesta menos de 1 USD más unos centavos de S3.

## A mano

### Pasos

```bash
# 1. en tu equipo: entrar a la instancia
ssh -i ~/.ssh/mi-llave.pem ubuntu@<IP_PUBLICA>

# 2. en la instancia: preparar (una vez; ~3 min)
curl -sSLO https://raw.githubusercontent.com/vcalderonc/Traffic-on-Barranquilla-Simulation/main/scripts/ec2/preparar.sh
bash preparar.sh

# 3. entrenar dentro de tmux (sigue aunque se caiga el SSH)
cd ~/Traffic-on-Barranquilla-Simulation
tmux new -s fase2
SEMILLAS=15 EPISODIOS=600 BUCKET=s3://<tu-bucket>/bq APAGAR=1 bash scripts/ec2/entrenar_fase2.sh
#   Ctrl-b d para salir de tmux; `tmux attach -t fase2` para volver
#   progreso: tail -f salidas/fase2/log_s1.txt

# 4. en tu equipo: traer los resultados (S3 o scp)
aws s3 sync s3://<tu-bucket>/bq/modelos/fase2 modelos/fase2
aws s3 sync s3://<tu-bucket>/bq/salidas/fase2 salidas/fase2
#   o: scp -i ~/.ssh/mi-llave.pem -r ubuntu@<IP>:Traffic-on-Barranquilla-Simulation/{modelos,salidas}/fase2 .
```

Para subir a S3, la instancia necesita un rol de IAM con permiso de escritura en ese
bucket (`s3:PutObject`, `s3:ListBucket`). Sin `BUCKET`, los resultados quedan en la
instancia y se traen con `scp` (sin `APAGAR=1` en ese caso).

## Después de entrenar

```bash
python -m bq_sim fase2 elegir             # tabla de candidatos (de validacion.json)
python -m bq_sim fase2 elegir --instalar  # copia el mejor a modelos/instructor_automovil.npz
python -m bq_sim visor                    # regrabar los recorridos con el instructor nuevo
python -m bq_sim solapes                  # medir que no queden carros encima de personas
```
