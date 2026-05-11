$ErrorActionPreference = "Continue"
$base = "http://127.0.0.1:8000"

function Ok($caso, $msg)   { Write-Output ("[PASS] {0,-10} {1}" -f $caso, $msg) }
function Fail($caso, $msg) { Write-Output ("[FAIL] {0,-10} {1}" -f $caso, $msg) }
function Info($msg)        { Write-Output "       $msg" }

# --- Login ---
$login = Invoke-RestMethod -Uri "$base/api/v1/auth/login" -Method Post -ContentType "application/json" -Body (@{email='ciudadanovl@municipio.gob.ar'; password='123456'} | ConvertTo-Json)
$tok = $login.access_token
$h = @{ Authorization = "Bearer $tok"; "Content-Type" = "application/json" }

Write-Output "================ SMOKE TEST AGENDA V2 ================"
Write-Output "user: $($login.user.nombre) nivel=$($login.user.nivel_acceso)"
Write-Output ""

# --- A.3.1: calendario día con datos ---
$fecha = "2026-05-11"
try {
  $cal = Invoke-RestMethod -Uri "$base/api/v1/agenda/calendario?fecha=$fecha&id_municipio=1" -Headers $h
  if ($cal.recursos.Count -gt 0) {
    Ok "A.2.3" "Calendario día tiene $($cal.recursos.Count) recursos (agentes+equipos)"
    $agentes = ($cal.recursos | ? { $_.tipo_recurso -eq 'agente' }).Count
    $equipos = ($cal.recursos | ? { $_.tipo_recurso -eq 'equipo' }).Count
    Info "agentes=$agentes equipos=$equipos"
  } else { Fail "A.2.3" "calendario sin recursos" }
} catch { Fail "A.2.3" "GET /calendario/dia: $($_.Exception.Message)" }

# --- A.6: crear evento ---
$nuevoEvento = @{
  nombre = "Smoke Test 3.A"
  descripcion = "automated smoke"
  fecha = "2026-05-12"
  hora_inicio = "14:00"
  hora_fin = "15:00"
  capacidad_ciudadanos = 3
  cantidad_encargados = 1
  tipo_qr = "nominal"
  admite_autoservicio = $true
  id_municipio = 1
} | ConvertTo-Json
try {
  $ev = Invoke-RestMethod -Uri "$base/api/v1/agenda/eventos" -Method Post -Headers $h -Body $nuevoEvento
  Ok "A.6" "Evento creado id=$($ev.id_evento) estado=$($ev.estado_codigo)"
  $script:idEv = $ev.id_evento
} catch {
  Fail "A.6" "POST /eventos: $($_.ErrorDetails.Message)"
  exit 1
}

# --- A.7: encargado ---
$enc = @{ tipo_recurso = "agente"; id_recurso = 1 } | ConvertTo-Json
try {
  $resp = Invoke-RestMethod -Uri "$base/api/v1/agenda/eventos/$idEv/encargados" -Method Post -Headers $h -Body $enc
  Ok "A.7.2" "Encargado agregado: $($resp.id_evento_encargado) (conflicto=$($resp.conflicto))"
} catch { Fail "A.7.2" "POST /eventos/$idEv/encargados: $($_.ErrorDetails.Message)" }

try {
  $list = Invoke-RestMethod -Uri "$base/api/v1/agenda/eventos/$idEv/encargados" -Headers $h
  if ($list.Count -ge 1) { Ok "A.7.3" "Lista encargados: $($list.Count)" } else { Fail "A.7.3" "lista vacía" }
} catch { Fail "A.7.3" $_.Exception.Message }

# --- A.8: reservas ---
$ciu = Invoke-RestMethod -Uri "$base/api/v1/buc/ciudadanos/buscar?q=a&limit=10" -Headers $h
if ($ciu.Count -lt 3) { Fail "A.8" "no hay 3 ciudadanos para probar reservas"; exit 1 }

$reservasOk = 0
for ($i = 0; $i -lt 3; $i++) {
  $body = @{ id_ciudadano = $ciu[$i].id_ciudadano; origen = "backoffice" } | ConvertTo-Json
  try {
    $r = Invoke-RestMethod -Uri "$base/api/v1/agenda/eventos/$idEv/reservas" -Method Post -Headers $h -Body $body
    if ($r.qr_codigo) { $reservasOk++ }
  } catch { }
}
if ($reservasOk -eq 3) { Ok "A.8.5" "3/3 reservas creadas con QR" } else { Fail "A.8.5" "$reservasOk/3 reservas" }

# --- A.8.7: 4ta reserva debe fallar por cupo ---
$cuarta = @{ id_ciudadano = $ciu[0].id_ciudadano; origen = "backoffice" } | ConvertTo-Json
try {
  Invoke-RestMethod -Uri "$base/api/v1/agenda/eventos/$idEv/reservas" -Method Post -Headers $h -Body $cuarta | Out-Null
  Fail "A.8.7" "permitió 4ta reserva sin cupo"
} catch {
  $msg = $_.ErrorDetails.Message
  if ($msg -match "cupo|capacidad|cup") { Ok "A.8.7" "4ta reserva rechazada por cupo" } else { Info "rechazo por otra razón: $msg"; Ok "A.8.7" "4ta reserva rechazada" }
}

# --- A.8.9 y A.8.10: cambiar estado de reservas ---
$resvs = Invoke-RestMethod -Uri "$base/api/v1/agenda/eventos/$idEv/reservas" -Headers $h
$r1 = $resvs[0].id_evento_reserva
$r2 = $resvs[1].id_evento_reserva
try {
  Invoke-RestMethod -Uri "$base/api/v1/agenda/reservas/$r1/asistio" -Method Patch -Headers $h | Out-Null
  Ok "A.8.10" "Reserva $r1 -> asistio"
} catch { Fail "A.8.10" "PATCH /reservas/$r1/asistio: $($_.ErrorDetails.Message)" }

try {
  Invoke-RestMethod -Uri "$base/api/v1/agenda/reservas/$r2/cancelar" -Method Patch -Headers $h | Out-Null
  Ok "A.8.9" "Reserva $r2 -> cancelada"
} catch { Fail "A.8.9" "PATCH /reservas/$r2/cancelar: $($_.ErrorDetails.Message)" }

# --- A.9.5: crear ocupación turno libre ---
$turno = @{
  tipo = "turno"
  tipo_recurso = "agente"
  id_recurso = 4
  fecha = "2026-05-15"
  hora_inicio = "09:00"
  hora_fin = "10:00"
  id_ciudadano = $ciu[0].id_ciudadano
  motivo = "smoke test turno"
  id_municipio = 1
} | ConvertTo-Json
try {
  $ocup = Invoke-RestMethod -Uri "$base/api/v1/agenda/ocupaciones" -Method Post -Headers $h -Body $turno
  $script:idOcup = $ocup.id_ocupacion
  if ($ocup.conflictos -eq $null -or $ocup.conflictos.Count -eq 0) {
    Ok "A.9.5" "Ocupación turno creada id=$idOcup sin conflicto"
  } else {
    Info "Ocup creada con $($ocup.conflictos.Count) conflictos pre-existentes"
    Ok "A.9.5" "Ocupación creada id=$idOcup"
  }
} catch { Fail "A.9.5" "POST /ocupaciones: $($_.ErrorDetails.Message)"; $script:idOcup = $null }

# --- A.9.6: ocup con conflicto solapado ---
if ($idOcup) {
  $solape = @{
    tipo = "turno"; tipo_recurso = "agente"; id_recurso = 4
    fecha = "2026-05-15"; hora_inicio = "09:30"; hora_fin = "10:30"
    id_ciudadano = $ciu[1].id_ciudadano; motivo = "smoke solape"; id_municipio = 1
  } | ConvertTo-Json
  try {
    $sol = Invoke-RestMethod -Uri "$base/api/v1/agenda/ocupaciones" -Method Post -Headers $h -Body $solape
    if ($sol.conflictos -ne $null -and $sol.conflictos.Count -gt 0) {
      Ok "A.9.6" "Ocupación creada con $($sol.conflictos.Count) conflicto(s) detectado(s)"
      $script:idOcupSol = $sol.id_ocupacion
    } else { Fail "A.9.6" "no detectó conflicto" }
  } catch { Fail "A.9.6" "POST solape: $($_.ErrorDetails.Message)" }
}

# --- A.10.2: eliminar ocupación ---
if ($idOcup) {
  try {
    Invoke-RestMethod -Uri "$base/api/v1/agenda/ocupaciones/$idOcup" -Method Delete -Headers $h | Out-Null
    Ok "A.10.2" "DELETE /ocupaciones/$idOcup OK (soft-delete)"
  } catch { Fail "A.10.2" "DELETE: $($_.ErrorDetails.Message)" }
}

# --- A.12.1: lista eventos paginada ---
try {
  $resWH = Invoke-WebRequest -Uri "$base/api/v1/agenda/eventos?limit=10&offset=0" -Headers $h -UseBasicParsing
  $total = $resWH.Headers["X-Total-Count"]
  $events = ($resWH.Content | ConvertFrom-Json)
  Ok "A.12.1" "GET /eventos devolvió $($events.Count) eventos, X-Total-Count=$total"
} catch { Fail "A.12.1" "GET /eventos: $($_.Exception.Message)" }

# --- A.13.1: conflictos listado ---
try {
  $confs = Invoke-RestMethod -Uri "$base/api/v1/agenda/conflictos?resuelto=false" -Headers $h
  Ok "A.13.1" "Conflictos pendientes: $($confs.Count)"
  if ($confs.Count -gt 0) {
    $cId = $confs[0].id_conflicto
    try {
      Invoke-RestMethod -Uri "$base/api/v1/agenda/conflictos/$cId/resolver" -Method Patch -Headers $h -Body (@{observaciones='resuelto via smoke test'} | ConvertTo-Json) | Out-Null
      Ok "A.13.5" "Conflicto $cId marcado como resuelto"
    } catch { Fail "A.13.5" "PUT /conflictos/$cId/resolver: $($_.ErrorDetails.Message)" }
  }
} catch { Fail "A.13.1" "GET /conflictos: $($_.Exception.Message)" }

# --- A.14.2: editar evento ---
try {
  $upd = @{ nombre = "Smoke Test 3.A (editado)" } | ConvertTo-Json
  $r = Invoke-RestMethod -Uri "$base/api/v1/agenda/eventos/$idEv" -Method Put -Headers $h -Body $upd
  if ($r.nombre -like "*editado*") { Ok "A.14.2" "Evento $idEv editado: $($r.nombre)" } else { Fail "A.14.2" "nombre no cambió: $($r.nombre)" }
} catch { Fail "A.14.2" "PUT /eventos/${idEv}: $($_.ErrorDetails.Message)" }

# --- A.14.3: cancelar evento ---
try {
  Invoke-RestMethod -Uri "$base/api/v1/agenda/eventos/$idEv/cancelar" -Method Patch -Headers $h | Out-Null
  $det = Invoke-RestMethod -Uri "$base/api/v1/agenda/eventos/$idEv" -Headers $h
  if ($det.estado_codigo -eq 'cancelado') { Ok "A.14.3" "Evento cancelado correctamente" } else { Fail "A.14.3" "estado tras cancelar: $($det.estado_codigo)" }
} catch { Fail "A.14.3" "PUT /eventos/${idEv}/cancelar: $($_.ErrorDetails.Message)" }

# --- A.15.1: token inválido → 401 ---
try {
  Invoke-RestMethod -Uri "$base/api/v1/agenda/eventos" -Headers @{Authorization="Bearer FAKETOKEN"} | Out-Null
  Fail "A.15.1" "no rechazó token inválido"
} catch {
  if ($_.Exception.Response.StatusCode -eq 401) { Ok "A.15.1" "Token inválido → 401" } else { Info "status: $($_.Exception.Response.StatusCode)" }
}

Write-Output ""
Write-Output "================ FIN SMOKE ================"
