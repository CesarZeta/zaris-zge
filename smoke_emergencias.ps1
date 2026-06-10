# smoke_emergencias.ps1 - Smoke del modulo Emergencias Fase 3 (local).
# Cubre las validaciones de cierre del plan PLAN_MODULO_EMERGENCIAS.md Fase 3:
# contacto eventual, busqueda unificada, evento + numero EM-YYYY-NNNNNN,
# FSM de estados, log append-only, promocion a BUC.
# Uso: backend local corriendo en 127.0.0.1:8000 con mig 81-83 aplicadas.
#   powershell -File smoke_emergencias.ps1

$ErrorActionPreference = "Stop"
$base = "http://127.0.0.1:8000"
$pass = 0; $fail = 0

function Assert($cond, $msg) {
    if ($cond) { $script:pass++; Write-Host "[OK]   $msg" }
    else { $script:fail++; Write-Host "[FAIL] $msg" }
}

function Invoke-Api($method, $path, $headers, $bodyObj) {
    $args2 = @{ Uri = "$base$path"; Method = $method; TimeoutSec = 15 }
    if ($headers) { $args2.Headers = $headers }
    if ($null -ne $bodyObj) {
        $args2.Body = [System.Text.Encoding]::UTF8.GetBytes(($bodyObj | ConvertTo-Json -Depth 6))
        $args2.ContentType = "application/json; charset=utf-8"
    }
    return Invoke-RestMethod @args2
}

function Get-StatusCode($scriptblock) {
    try { & $scriptblock | Out-Null; return 200 }
    catch { return $_.Exception.Response.StatusCode.value__ }
}

# ---- login ----
$login = Invoke-Api POST "/api/v1/auth/login" $null @{ email = "ciudadanovl@municipio.gob.ar"; password = "123456" }
$H = @{ Authorization = "Bearer $($login.access_token)" }
Assert ($null -ne $login.access_token) "login admin local"

# ---- datos base ----
$subPol = (Invoke-Api GET "/api/v1/emergencias/tipos?id_subarea=90" $H $null)
Assert ($subPol.Count -eq 34) "34 tipos policia"
$robo = $subPol | Where-Object { $_.codigo -eq 'ROBO' }
$agradec = $subPol | Where-Object { $_.codigo -eq 'AGRADECIMIENTO' }
$tipoDc = (Invoke-Api GET "/api/v1/emergencias/tipos?id_subarea=91" $H $null) | Where-Object { $_.codigo -eq 'INCENDIO' }
$canales = Invoke-Api GET "/api/v1/emergencias/canales" $H $null
$canalTel = $canales | Where-Object { $_.codigo -eq 'LLAMADA_TEL' }
$orgs = Invoke-Api GET "/api/v1/emergencias/organismos" $H $null
$bomberos = $orgs | Where-Object { $_.codigo -eq 'BOMBEROS' }
$subtipoRobo = (Invoke-Api GET "/api/v1/emergencias/tipos/$($robo.id_emergencia_tipo)/subtipos" $H $null) | Where-Object { $_.codigo -eq 'VIA_PUBLICA' }

# ciudadano BUC de referencia (uno con telefono usable)
$bucList = Invoke-Api GET "/api/v1/buc/ciudadanos/buscar?q=a&limit=50" $H $null
$buc = $bucList | Where-Object { ($_.doc_nro -replace '\D','').Length -ge 6 } | Select-Object -First 1
Assert ($null -ne $buc) "ciudadano BUC de referencia encontrado (doc $($buc.doc_nro))"

# ---- busqueda unificada ----
$r = Invoke-Api GET "/api/v1/emergencias/denunciantes/buscar?dni=$($buc.doc_nro)" $H $null
Assert ($r.origen -eq 'BUC' -and $r.matches.Count -ge 1) "buscar dni BUC -> origen=BUC"
$r = Invoke-Api GET "/api/v1/emergencias/denunciantes/buscar?nombre=$($buc.apellido)" $H $null
Assert ($r.origen -eq 'BUC') "buscar nombre BUC -> origen=BUC"
# DNI aleatorio garantizado inexistente (local puede tener residuos de tests)
$dniNuevo = $null
foreach ($i in 1..10) {
    $cand = (Get-Random -Minimum 60000000 -Maximum 69999999).ToString()
    $r = Invoke-Api GET "/api/v1/emergencias/denunciantes/buscar?dni=$cand" $H $null
    if ($r.origen -eq 'NUEVO') { $dniNuevo = $cand; break }
}
Assert ($null -ne $dniNuevo -and $r.criterio -eq 'dni') "buscar dni inexistente ($dniNuevo) -> origen=NUEVO"

# ---- contacto eventual ----
# telefono y nombre unicos por corrida (los runs previos promueven a BUC y
# la busqueda unificada prioriza BUC — comportamiento correcto del sistema)
$telNuevo = "11$dniNuevo"
$nombreUnico = "Prueba Smoke $dniNuevo"
$ct = Invoke-Api POST "/api/v1/emergencias/contactos-eventuales" $H @{
    dni = $dniNuevo; nombre_apellido = $nombreUnico
    telefono = "11-$dniNuevo"; direccion = "Calle Falsa 123, La Plata"
    contacto_alt_nombre = "Vecino Alt"; contacto_alt_telefono = "2215559999"
}
Assert ($ct.id_emergencia_contacto_eventual -gt 0 -and $ct.telefono -eq $telNuevo) "POST contacto eventual (telefono normalizado)"
$r = Invoke-Api GET "/api/v1/emergencias/denunciantes/buscar?dni=$dniNuevo" $H $null
Assert ($r.origen -eq 'EVENTUAL') "buscar dni cargado -> origen=EVENTUAL"
$r = Invoke-Api GET "/api/v1/emergencias/denunciantes/buscar?telefono=11 $dniNuevo" $H $null
Assert ($r.origen -eq 'EVENTUAL') "buscar por telefono -> origen=EVENTUAL"
$r = Invoke-Api GET "/api/v1/emergencias/denunciantes/buscar?nombre=smoke $dniNuevo" $H $null
Assert ($r.origen -eq 'EVENTUAL') "buscar por nombre multi-token -> origen=EVENTUAL"
$code = Get-StatusCode { Invoke-Api POST "/api/v1/emergencias/contactos-eventuales" $H @{ dni = $dniNuevo; nombre_apellido = "Dup"; telefono = "111111"; direccion = "x y z" } }
Assert ($code -eq 409) "contacto duplicado por dni -> 409"

# ---- evento 1: ciclo completo PENDIENTE -> ... -> RESUELTO ----
$ev1 = Invoke-Api POST "/api/v1/emergencias/eventos" $H @{
    id_subarea = 90; id_tipo = $robo.id_emergencia_tipo
    id_subtipo = $subtipoRobo.id_emergencia_subtipo
    id_canal_ingreso = $canalTel.id_emergencia_canal_ingreso
    denunciante_anonimo = $false
    id_contacto_eventual = $ct.id_emergencia_contacto_eventual
    direccion_evento = "Av. 7 entre 47 y 48, La Plata"
    observaciones_recepcion = "Robo en via publica reportado por smoke"
}
Assert ($ev1.numero_operativo -match '^EM-\d{4}-\d{6}$') "numero operativo $($ev1.numero_operativo) formato EM-YYYY-NNNNNN"
Assert ($ev1.estado_codigo -eq 'PENDIENTE') "evento nace PENDIENTE"
Assert ($ev1.prioridad_codigo -eq 'P1') "prioridad autocompletada del tipo (P1)"
Assert ($ev1.organismo_codigo -eq 'POLICIA_911_PBA') "organismo default del tipo precargado"
Assert ($ev1.denunciante_nombre -eq $nombreUnico) "denunciante resuelto"
$log = Invoke-Api GET "/api/v1/emergencias/eventos/$($ev1.id_emergencia_evento)/log" $H $null
Assert ($log.Count -eq 1 -and $log[0].tipo_accion -eq 'CREACION') "log CREACION registrado"

$ev1b = Invoke-Api POST "/api/v1/emergencias/eventos/$($ev1.id_emergencia_evento)/cambiar-estado" $H @{ nuevo_estado = "EN_PREPARACION"; observaciones = "preparando movil" }
Assert ($ev1b.estado_codigo -eq 'EN_PREPARACION') "PENDIENTE -> EN_PREPARACION"
$ev1c = Invoke-Api POST "/api/v1/emergencias/eventos/$($ev1.id_emergencia_evento)/cambiar-estado" $H @{ nuevo_estado = "EN_CAMINO" }
Assert ($null -ne $ev1c.fecha_hora_despacho) "EN_CAMINO setea fecha_hora_despacho"
$ev1d = Invoke-Api POST "/api/v1/emergencias/eventos/$($ev1.id_emergencia_evento)/marcar-en-sitio" $H $null
Assert ($ev1d.estado_codigo -eq 'EN_SITIO' -and $null -ne $ev1d.fecha_hora_arribo) "marcar-en-sitio setea fecha_hora_arribo"
$ev1e = Invoke-Api POST "/api/v1/emergencias/eventos/$($ev1.id_emergencia_evento)/cerrar" $H @{ veracidad = "CONFIRMADA"; terminal_positivo = $true; observaciones_cierre = "resuelto en sitio" }
Assert ($ev1e.estado_codigo -eq 'RESUELTO' -and $ev1e.veracidad -eq 'CONFIRMADA' -and $null -ne $ev1e.fecha_hora_cierre) "cierre RESUELTO + veracidad + fecha_hora_cierre"
$log = Invoke-Api GET "/api/v1/emergencias/eventos/$($ev1.id_emergencia_evento)/log" $H $null
Assert ($log.Count -eq 5) "log con 5 entradas (creacion + 3 cambios + cierre)"
$code = Get-StatusCode { Invoke-Api POST "/api/v1/emergencias/eventos/$($ev1.id_emergencia_evento)/cambiar-estado" $H @{ nuevo_estado = "EN_CAMINO" } }
Assert ($code -eq 422) "transicion desde terminal -> 422"
$code = Get-StatusCode { Invoke-Api PATCH "/api/v1/emergencias/eventos/$($ev1.id_emergencia_evento)" $H @{ direccion_evento = "otra" } }
Assert ($code -eq 422) "editar evento terminal -> 422"

# ---- evento 2: anonimo + derivacion -> RESUELTO ----
$ev2 = Invoke-Api POST "/api/v1/emergencias/eventos" $H @{
    id_subarea = 91; id_tipo = $tipoDc.id_emergencia_tipo
    id_canal_ingreso = $canalTel.id_emergencia_canal_ingreso
    denunciante_anonimo = $true
    direccion_evento = "Diagonal 74 y 60, La Plata"
}
Assert ($ev2.denunciante_nombre -eq 'Anonimo' -and $ev2.prioridad_codigo -eq 'P1') "evento anonimo DC (INCENDIO P1)"
$ev2b = Invoke-Api POST "/api/v1/emergencias/eventos/$($ev2.id_emergencia_evento)/derivar" $H @{ id_organismo = $bomberos.id_emergencia_organismo_derivacion; observaciones = "derivado a bomberos" }
Assert ($ev2b.estado_codigo -eq 'DERIVADO' -and $ev2b.organismo_codigo -eq 'BOMBEROS') "PENDIENTE -> DERIVADO con organismo"
$ev2c = Invoke-Api POST "/api/v1/emergencias/eventos/$($ev2.id_emergencia_evento)/cerrar" $H @{ veracidad = "NO_VERIFICABLE"; terminal_positivo = $true }
Assert ($ev2c.estado_codigo -eq 'RESUELTO') "DERIVADO -> RESUELTO"

# ---- evento 3: desestimado con falsa alarma ----
$ev3 = Invoke-Api POST "/api/v1/emergencias/eventos" $H @{
    id_subarea = 90; id_tipo = $agradec.id_emergencia_tipo
    id_canal_ingreso = $canalTel.id_emergencia_canal_ingreso
    denunciante_anonimo = $true
    direccion_evento = "Sin direccion relevante 1"
}
Assert ($ev3.prioridad_codigo -eq 'P3' -and $null -eq $ev3.organismo_codigo) "tipo sin organismo default (P3)"
$ev3b = Invoke-Api POST "/api/v1/emergencias/eventos/$($ev3.id_emergencia_evento)/cerrar" $H @{ veracidad = "FALSA_ALARMA"; terminal_positivo = $false; observaciones_cierre = "broma" }
Assert ($ev3b.estado_codigo -eq 'DESESTIMADO' -and $ev3b.veracidad -eq 'FALSA_ALARMA') "PENDIENTE -> DESESTIMADO FALSA_ALARMA"

# ---- validaciones del POST ----
$code = Get-StatusCode { Invoke-Api POST "/api/v1/emergencias/eventos" $H @{ id_subarea = 91; id_tipo = $robo.id_emergencia_tipo; id_canal_ingreso = $canalTel.id_emergencia_canal_ingreso; denunciante_anonimo = $true; direccion_evento = "x y z" } }
Assert ($code -eq 422) "tipo de otra subarea -> 422"
$code = Get-StatusCode { Invoke-Api POST "/api/v1/emergencias/eventos" $H @{ id_subarea = 90; id_tipo = $robo.id_emergencia_tipo; id_canal_ingreso = $canalTel.id_emergencia_canal_ingreso; denunciante_anonimo = $true; id_ciudadano_buc = $buc.id_ciudadano; direccion_evento = "x y z" } }
Assert ($code -eq 422) "anonimo + ciudadano -> 422"
$code = Get-StatusCode { Invoke-Api POST "/api/v1/emergencias/eventos" $H @{ id_subarea = 90; id_tipo = $robo.id_emergencia_tipo; id_canal_ingreso = $canalTel.id_emergencia_canal_ingreso; denunciante_anonimo = $false; direccion_evento = "x y z" } }
Assert ($code -eq 422) "no anonimo sin denunciante -> 422"

# ---- promocion a BUC ----
$ev4 = Invoke-Api POST "/api/v1/emergencias/eventos" $H @{
    id_subarea = 90; id_tipo = $robo.id_emergencia_tipo
    id_canal_ingreso = $canalTel.id_emergencia_canal_ingreso
    denunciante_anonimo = $false
    id_contacto_eventual = $ct.id_emergencia_contacto_eventual
    direccion_evento = "Calle 50 nro 1234"
}
$code = Get-StatusCode { Invoke-Api POST "/api/v1/emergencias/contactos-eventuales/$($ct.id_emergencia_contacto_eventual)/promover-a-buc" $H @{} }
Assert ($code -eq 422) "promover sin datos -> 422 (pide apellido/nombre/email)"
$prom = Invoke-Api POST "/api/v1/emergencias/contactos-eventuales/$($ct.id_emergencia_contacto_eventual)/promover-a-buc" $H @{ apellido = "Smoke"; nombre = "Eventual"; email = "smoke.eventual@test.local" }
Assert ($prom.ciudadano_creado -eq $true -and $prom.eventos_reasignados -eq 2) "promocion crea ciudadano y reasigna 2 eventos"
$ev4b = Invoke-Api GET "/api/v1/emergencias/eventos/$($ev4.id_emergencia_evento)" $H $null
Assert ($ev4b.id_ciudadano_buc -eq $prom.id_ciudadano -and $null -eq $ev4b.id_contacto_eventual) "evento reapuntado a BUC, contacto en NULL"
$r = Invoke-Api GET "/api/v1/emergencias/denunciantes/buscar?dni=$dniNuevo" $H $null
Assert ($r.origen -eq 'BUC') "buscar dni promovido -> origen=BUC"
$log4 = Invoke-Api GET "/api/v1/emergencias/eventos/$($ev4.id_emergencia_evento)/log" $H $null
Assert (@($log4 | Where-Object { $_.tipo_accion -eq 'PROMOCION_BUC' }).Count -eq 1) "log PROMOCION_BUC en el evento"
$code = Get-StatusCode { Invoke-Api POST "/api/v1/emergencias/contactos-eventuales/$($ct.id_emergencia_contacto_eventual)/promover-a-buc" $H @{ apellido = "X"; nombre = "Y"; email = "z@z.z" } }
Assert ($code -eq 409) "re-promover -> 409"

# ---- listados ----
$ab = Invoke-Api GET "/api/v1/emergencias/eventos/abiertos" $H $null
Assert (@($ab | Where-Object { $_.id_emergencia_evento -eq $ev4.id_emergencia_evento }).Count -eq 1) "evento abierto aparece en /eventos/abiertos"
Assert (@($ab | Where-Object { $_.estado_codigo -in @('RESUELTO','DESESTIMADO') }).Count -eq 0) "abiertos no incluye terminales"
$lista = Invoke-Api GET "/api/v1/emergencias/eventos?estado=RESUELTO" $H $null
Assert (($lista | Where-Object { $_.estado_codigo -ne 'RESUELTO' }).Count -eq 0) "filtro estado=RESUELTO"

# ---- PATCH edicion ----
$ev4c = Invoke-Api PATCH "/api/v1/emergencias/eventos/$($ev4.id_emergencia_evento)" $H @{ id_prioridad = ($subPol[0].id_prioridad_default); referencia_ubicacion = "frente a la plaza" }
Assert ($ev4c.referencia_ubicacion -eq 'frente a la plaza') "PATCH campos editables"

# ---- sin JWT ----
$code = Get-StatusCode { Invoke-RestMethod -Uri "$base/api/v1/emergencias/eventos" -TimeoutSec 10 }
Assert ($code -eq 401) "GET /eventos sin JWT -> 401"

Write-Host ""
Write-Host "==== RESULTADO: $pass OK / $fail FAIL ===="
if ($fail -gt 0) { exit 1 }
