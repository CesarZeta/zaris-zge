---
name: feedback-nominatim-filtrar-pois
description: "Para filtrar POIs (comercios) en /geo/buscar y dejar solo direcciones, pedir limit alto a Nominatim y reescribir display_name desde `address` cuando viene un POI sobre una dirección válida."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: dfc52c6d-67d2-4a36-93ca-2b5655f60612
---

Cuando un endpoint /geo/buscar (proxy a Nominatim) tiene que servir como input de domicilio (no de POI), no alcanza con filtrar por class del response. Tres trampas reales cazadas 2026-05-15:

**Trampa 1 — `layer=address` de Nominatim es DEMASIADO restrictivo.** Excluye `highway/secondary` (calle sin número exacto), que sí es válida como "Av Maipú 1500" cuando el numero exacto no está en OSM. Resultado: query válida devuelve 0. Mejor NO usar `layer=address`, filtrar manualmente.

**Trampa 2 — `limit` upstream tiene que ser muchísimo más alto que el limit que devolvés al cliente.** Para queries genéricas (`Av Maipu 1500 Vicente Lopez`), Nominatim puede devolver 15+ POIs antes del primer `highway` válido. Si pedís `limit*3` upstream, filtrás todo y devolvés `[]`. Pedir el máximo que Nominatim acepta (40) cuando hay filtro activo.

**Trampa 3 — `class=building` + `type=commercial` puede ser la dirección correcta.** Nominatim a veces devuelve `Av Córdoba 1351 CABA` etiquetado como "Warner Chappell Music Argentina, 1351, Avenida Córdoba..." porque ese edificio aloja un comercio. El `address.road` + `address.house_number` son correctos. Si lo descartás por blacklist, perdés direcciones reales. La solución que funcionó: **mantener el resultado pero reescribir `display_name` desde `address`** para que el usuario vea `1351 Avenida Córdoba, Retiro, Comuna 1, CABA` en lugar del nombre del comercio.

**Why:** En la implementación inicial del filtro POI en `backend/app/api/routes/geo.py::buscar_direccion(solo_direcciones=true)`, las 3 trampas las cazó el usuario en QA visual una por una, no el smoke automático. Cada una requirió un reinicio de uvicorn y un round-trip.

**How to apply:** En cualquier endpoint nuevo que sirva direcciones para formularios:
- NO usar `layer=address` upstream.
- Pedir `limit=40` upstream cuando hay filtro POI activo, devolver los primeros N válidos.
- Reescribir display_name desde `address` cuando el resultado tiene `address.road` válido pero `display_name` no arranca con la calle o el house_number.
- Blacklist por `class` (amenity/shop/office/tourism/leisure/craft/healthcare/club/emergency/man_made) — esos siempre van afuera.
- Blacklist por `type` cuando `class=building` (commercial/retail/office/hotel/restaurant/hospital/school/etc.) — solo si el resultado NO tiene `address.road` válido. Si tiene road+number, mantener.

Referencia canónica: `backend/app/api/routes/geo.py::buscar_direccion` después del commit `164b817`.
