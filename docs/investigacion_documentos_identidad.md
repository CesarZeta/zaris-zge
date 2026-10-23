# Documentos de identificación de personas y empresas en Hispanoamérica — investigación para el módulo parametrizable por país (ZARIS)

> Investigación hecha el 2026-10-23. Es solo investigación: no se tocó el repositorio.
> Referencia de Argentina en ZARIS: `backend/app/schemas/buc.py::_validar_modulo11` (CUIL/CUIT) y `backend/app/schemas/publico_alta.py` (reusa ese validador). El plan `PLAN_MULTI_MUNICIPIO.md` §7 ya decidió guardar el documento como (país, tipo, número).
>
> **Convenciones de este informe**
> - **Normativo**: lo dice una norma o el organismo emisor (o el organismo lo declaró ante la OCDE en su ficha oficial de TIN).
> - **Técnico**: lo dice una biblioteca de validación muy usada (python-stdnum 2.2; stdnum para JS 1.12.6), que no es fuente oficial.
> - **Habitual**: uso corriente informado por prensa o sitios comerciales; no es norma.
> - **NO VERIFICADO**: no se encontró fuente que lo confirme. Todos están juntos en la lista final.
> - Ninguno de los algoritmos se completó de memoria: cada uno sale del código fuente de una biblioteca citada o de un documento, y 17 de ellos se volvieron a calcular con un motor propio y se contrastaron contra la biblioteca (ver §5.4).

---

## 1. Resumen ejecutivo

1. En los 18 países hay un documento nacional de identidad y un identificador tributario. En al menos 14 de ellos el identificador tributario de la persona **sale del número del documento**: es el mismo número, o el número más un dígito verificador o un sufijo (CUIL = prefijo + DNI + DV; RUC de Perú = 10 + DNI + DV; NIT de Colombia = cédula + DV; RUC de Ecuador = cédula + 001; NIT de El Salvador = DUI; NIT de Guatemala = 9 primeros dígitos del CUI desde 2025).
2. La mayoría son solo dígitos, pero hay alfanuméricos de verdad: CURP y RFC (México), RIF (Venezuela, letra inicial), RUT de Chile y NIT de Guatemala (DV «K»), carácter de control del DNI de Perú (dígito o letra), complemento de la cédula de Bolivia, cédula de Panamá (letras y partes con guiones) y NIE y NIF de España.
3. Los identificadores tributarios tienen DV en 13 países. Los documentos de identidad de persona **no** tienen DV en Argentina, Paraguay, Bolivia, Colombia, Venezuela, Honduras, Costa Rica y Panamá: ahí solo se puede validar el formato.
4. **Un solo algoritmo parametrizable** cubre 17 esquemas de 12 países (más España): suma ponderada, resto y una tabla que traduce el resto en el carácter verificador. Se contrastó contra python-stdnum en 20.000 casos aleatorios por esquema, sin una sola diferencia. Con Luhn y un validador «compuesto» por reglas se cubre todo, salvo el DV de dos dígitos del RUC de Panamá, que necesita código propio.
5. Pocos organismos publican el algoritmo. Hay fuente normativa para Chile (SII ante la OCDE), Colombia (DIAN, Orden Administrativa 4 de 1989), Panamá (documento técnico de la DGI) y Uruguay (el decreto dice «módulo diez» pero no da los pesos). Para el resto, la fuente es técnica (bibliotecas).
6. Hay números que cambiaron hace poco: en El Salvador el NIT de las personas pasó a ser el DUI (2021-2022); en Guatemala el NIT pasa a ser el CUI (Resolución SAT-DSI-393-2025); en Venezuela hay nueva providencia del RIF (2026); el RUC jurídico de Panamá cambió de formato en 2014; en Argentina los prefijos del CUIT de personas ya no indican el sexo.
7. Hay ley general de datos personales en 14 países. No la hay en Bolivia, Venezuela, Guatemala ni Honduras. Paraguay (Ley 7593/2025) y Chile (Ley 21.719) tienen leyes nuevas que entran en vigor entre 2026 y 2027.
8. La propuesta: un catálogo global `tipo_documento` por país (datos que edita el super administrador), cuatro algoritmos en código (ponderado, Luhn, compuesto y el DV de Panamá), validadores de componentes (fecha, catálogo) y dos endpoints: validar y configurar. Ningún tipo se guarda si sus ejemplos no pasan la autoprueba.
9. Riesgos de modelado: números no únicos (Bolivia), números válidos que no cumplen su propio DV (República Dominicana, RFC de México), separadores que tienen significado (Panamá y Costa Rica), DV de dos dígitos (Panamá) y una sola persona con varios documentos válidos a la vez.
10. Honduras, Nicaragua, Bolivia y Cuba no tienen fuente oficial del formato, y el DV de Panamá no coincide en 4 de 7 ejemplos. Quedan marcados como NO VERIFICADO en §9.

---

## 2. Tabla comparativa por país

Leyenda de la columna DV: **N** = DV con fuente normativa · **T** = DV con fuente técnica (biblioteca) · **—** = no tiene DV · **?** = no verificado.

| País | Documento de persona (emisor) | Formato normalizado (DV) | ID fiscal de persona | ID fiscal de empresa (formato, DV) | Extranjeros residentes | Ley de datos personales |
|---|---|---|---|---|---|---|
| AR | DNI (RENAPER) | 7–8 dígitos (—) | CUIL / CUIT: 11 dígitos = prefijo + DNI + DV (T) | CUIT: 11 dígitos, prefijo 30/33/34 (T) | DNI de extranjero (mismo esquema) | Ley 25.326 |
| UY | CI (DNIC) | 7 dígitos + DV (pesos T; «módulo diez» N) | CI; RUT si tiene actividad | RUT: 12 dígitos (T) | CI (DNIC); NIE de la DGI: 9 dígitos que empiezan con 9 (? DV) | Ley 18.331 |
| CL | RUN (Registro Civil) | 7–8 dígitos + DV 0-9/K (N) | RUT = RUN | RUT (SII), mismo algoritmo (N) | RUN si es residente; RUT del SII si no | Ley 19.628 → Ley 21.719 (desde el 1-12-2026) |
| PY | CI (Policía Nacional) | 5–7 dígitos (—) (?) | RUC = CI + DV (T) | RUC: 8 dígitos desde 80000000 + DV (T) | CI de extranjero (?) | Ley 7593/2025 (vigencia 2027) |
| BO | CI (SEGIP) | número + complemento opcional (—) (?) | NIT (SIN) (?) | NIT (?) | CI de extranjero (?) | Sin ley general |
| PE | DNI (RENIEC) | 8 dígitos + carácter de control opcional, dígito o letra (T) | RUC 10 + DNI + DV (T) | RUC 20 + 8 + DV (T) | Carné de extranjería (Migraciones) (?) | Ley 29733 + DS 016-2024-JUS |
| EC | Cédula (Registro Civil) | 10 dígitos (Luhn, T) | RUC = cédula + 001 | RUC: 13 dígitos (T) | Cédula de extranjero residente | LOPDP 2021 |
| CO | CC (Registraduría) | hasta 10 dígitos (—) | NIT = CC + DV (N) | NIT: 9 dígitos + DV (N) | CE / PEP / PPT (Migración Colombia) (?) | Ley 1581 de 2012 |
| VE | Cédula V/E (SAIME) | letra + hasta 8 dígitos (—) (?) | RIF V/E + 8 + DV (T) | RIF J/G + 8 + DV (T) | Cédula «E» | Sin ley especial |
| MX | CURP (RENAPO) | 18 caracteres alfanuméricos (DV T; estructura N) | RFC: 13 caracteres (DV T) | RFC: 12 caracteres (DV T) | CURP de extranjero residente (?) | LGPDPPSO y LFPDPPP (DOF 20-03-2025) |
| GT | DPI / CUI (RENAP) | 13 dígitos = 8 + DV + depto + muni (estructura N, DV T) | NIT; desde 2025 = 9 primeros dígitos del CUI | NIT: 2–12 caracteres, DV 0-9/K (T) | CUI con casillas de inscripción (N) | Sin ley general (LAIP, Decreto 57-2008) |
| HN | DNI (RNP) | 13 dígitos (—) (?) | RTN: 14 dígitos = DNI + 1 (?) | RTN: 14 dígitos (?) | (?) | Sin ley general verificada |
| SV | DUI (RNPN) | 8 + DV (?) | NIT = DUI desde 2022 (N) | NIT: 14 dígitos (T) | Carné de residente (?); conserva el NIT de 14 | Ley para la Protección de Datos Personales (D.L. 144/2024) |
| NI | Cédula (CSE) | (?) | RUC (?) | RUC (?) | (?) | Ley 787 de 2012 |
| CR | Cédula de identidad (TSE) | 9 dígitos, provincia-tomo-asiento (—) | la misma cédula | Cédula jurídica: 10 dígitos (—) | DIMEX: 11–12 dígitos; NITE | Ley 8968 |
| PA | Cédula (Tribunal Electoral) | partes con letras y guiones (—) | RUC = cédula + DV de 2 dígitos (N, con conflicto) | RUC del Registro Público + DV de 2 dígitos | Cédula «E-»; NT de la DGI | Ley 81 de 2019 + DE 285 de 2021 |
| CU | Carné de identidad (MININT) | 11 dígitos con fecha de nacimiento (? DV) | (?) | NIT de la ONAT (?) | (?) | Ley 149 de 2022 |
| DO | Cédula (JCE) | 11 dígitos (Luhn, T, con excepciones) | RNC = cédula | RNC: 9 dígitos (T) | Cédula de extranjero (?) | Ley 172-13 |
| ES (anexo) | DNI (Policía) | 8 dígitos + letra (T) | NIF = DNI | NIF de entidades: letra + 7 + control (T) | NIE: X/Y/Z + 7 + letra (T) | RGPD + LO 3/2018 |

---

## 3. Detalle por país

Formato de cada ficha: nombre y sigla · organismo emisor · formato (normativo o habitual) · DV y algoritmo · ejemplo válido con su fuente · si el número es permanente · normas.
Las referencias entre corchetes [F#] remiten a §8 (fuentes).

### 3.1 Argentina (AR)

**DNI — Documento Nacional de Identidad.** Lo emite el Registro Nacional de las Personas (RENAPER), con base en la **Ley 17.671**. La Disposición RENAPER 82/2020 cita el art. 7 (número fijo e invariable, salvo error comprobado) y el art. 11 (el RENAPER es el único emisor) [F2].
- Formato técnico: 7 u 8 dígitos; se escribe `##.###.###`; se normaliza quitando puntos y espacios [F70 `stdnum.ar.dni`]. ZARIS acepta lo mismo hoy, y el login toma «solo dígitos, 7 u 8» como DNI.
- Sin DV. El número es permanente.
- Documentos viejos de menos de 7 dígitos (libreta de enrolamiento o cívica): **NO VERIFICADO** si siguen vigentes como identificación.

**CUIL — Código Único de Identificación Laboral / CUIT — Clave Única de Identificación Tributaria / CDI / CIE.** La OCDE informa que el CUIL «se otorga automáticamente y en simultáneo con el DNI», que la AFIP (hoy ARCA) asigna el CUIT y que existen el CDI (Clave de Identificación, para quien no necesita CUIT ni CUIL) y el CIE (inversores extranjeros) [F1]. Que el CUIL lo asigne la ANSES: **NO VERIFICADO** (la ficha de la OCDE no nombra al emisor).
- Estructura normativa [F1]: 11 dígitos. Los 2 primeros indican el tipo de persona: **20, 23, 24 o 27 «asignados al azar» y sin distinción binaria** para personas, y **30 o 33** para personas jurídicas. Los 8 siguientes son el DNI (persona) o un número que asigna la AFIP (persona jurídica). El último es el verificador.
- **Contradicción:** la misma ficha de la OCDE dice que el verificador «se asigna al azar». Las fuentes técnicas, y también el validador que ZARIS usa hoy, lo calculan así:
  - **Algoritmo técnico** [F70 `stdnum.ar.cuit`; F71 Wikipedia]: pesos `5,4,3,2,7,6,5,4,3,2` sobre los 10 primeros dígitos, de izquierda a derecha. r = S mod 11. DV = 0 si r = 0; DV = 11 − r si r ≥ 2.
  - **Resto 1** (DV sería 10): según Wikipedia, la AFIP cambia el prefijo a 23 (o 33) y el DV queda en 9 (hombres y empresas) o 4 (mujeres) [F71]. Con el prefijo 23 la suma vuelve a dar un DV válido sin regla especial (comprobado por cálculo propio). python-stdnum **y ZARIS** aceptan DV 9 con resto 1 sin importar el prefijo, así que aceptan números como `20-xxxxxxxx-9` que la AFIP no emitiría.
  - Prefijos que acepta stdnum: 20, 23, 24, 27, 30, 33, 34, 50, 51, 55 [F70]. Wikipedia suma 25 y 26 [F71]. ZARIS hoy no valida el prefijo.
- Ejemplo válido: `20-26756539-3` [F70, verificado ejecutando la biblioteca].
- El número es permanente, con la salvedad de la regla del prefijo 23.

**Ley de datos personales:** Ley 25.326 (sancionada el 4-10-2000; modificada por la Ley 26.343) [F3].

### 3.2 Uruguay (UY)

**CI — Cédula de Identidad.** La emite la Dirección Nacional de Identificación Civil (DNIC).
- Normativo: 7 números más un dígito verificador [F4, OCDE UY]. El Decreto 501/978, art. 2, dice que el número de la persona física es una sucesión natural «y la cifra del dígito verificador resultante de la aplicación del **módulo diez**», sin indicar pesos [F5].
- **Algoritmo técnico** [F72 `uy/cedula`; F73 ci_js]: si el número tiene 6 dígitos, se completa con un 0 a la izquierda. Pesos `2,9,8,7,6,3,4` de izquierda a derecha. DV = (10 − (S mod 10)) mod 10. Cuadra con dos ejemplos de fuentes secundarias, recalculados aquí: `1.234.567-2` (S = 148) y `4.378.273-8` (S = 192). Los pesos no tienen fuente oficial.
- Se escribe `#.###.###-#`. El número es permanente.

**NIE — Número de Identificación de Extranjero (DGI).** 9 dígitos con el formato `9NNNNNNN` + DV, para extranjeros que no tienen CI ni RUT [F4]. **Algoritmo NO VERIFICADO**: stdnum para JS usa pesos `5,4,3,2,9,8,7,6` y DV = (11 − r) mod 10, pero su propio autor anota que no encontró el algoritmo [F72 `uy/nie`].

**RUT — Registro Único Tributario (DGI).** Lo usan las personas jurídicas y las personas físicas con actividad empresarial. Una persona sin RUT usa su CI como identificador tributario [F4].
- Normativo: 12 dígitos [F4].
- Técnico [F70 `stdnum.uy.rut`, que cita el modelo de datos de AGESIC]: 2 dígitos de registro (01 a 22) + 6 de secuencia (distintos de 000000) + `001` + DV. Pesos `4,3,2,9,8,7,6,5,4,3,2` sobre los 11 primeros dígitos. DV = (−S) mod 11; **si da 10, el número no es válido**.
- Ejemplo: `21-100342-001-7` [F70, verificado].

**Ley de datos personales:** Ley 18.331 (2008) y su reglamento, el Decreto 414/009 [F6].

### 3.3 Chile (CL)

**RUN — Rol Único Nacional (Servicio de Registro Civil e Identificación) / RUT — Rol Único Tributario (SII).** Para chilenos y extranjeros residentes, el RUN que asigna el Registro Civil también es el RUT. Las entidades y los extranjeros no residentes reciben RUT del SII. El registro lo creó el **Decreto N° 3 de 1969 del Ministerio de Hacienda**. El número es **personal, intransferible y no se reasigna nunca** [F7, OCDE CL].
- Normativo: formato `xx.xxx.xxx-x`; el DV es un dígito o la letra K, por «módulo 11»: K si el resultado es 10, 0 si es 11 [F7].
- **Algoritmo** [F70 `stdnum.cl.rut`, equivalente]: pesos `2,3,4,5,6,7` aplicados de derecha a izquierda, en ciclo. DV = 11 − (S mod 11); 11 → `0`; 10 → `K`.
- Ejemplo: `12.531.909-2` [F70, verificado]. Personas: 7 u 8 dígitos más DV.

**Ley de datos personales:** Ley 19.628 (1999), vigente. La **Ley 21.719** se publicó el 13-12-2024 y entra en vigencia el 1-12-2026; el Boletín 18.623-07 propone pasar esa fecha al 1-12-2027 y estaba en primer trámite al 23-10-2026 [F8].

### 3.4 Paraguay (PY)

**CI — Cédula de Identidad Civil.** La emite la Policía Nacional (Departamento de Identificaciones) [F72 `py/cedula`].
- Técnico: 5 a 7 dígitos, sin DV [F72, que cita Wikipedia]. Fuente oficial del formato: **NO VERIFICADO**.
- Hay rangos de números bloqueados, que vienen del cambio de sistema de 1994-1995 [F9, Última Hora 2026].

**RUC — Registro Único del Contribuyente.** Lo administra la DNIT (Dirección Nacional de Ingresos Tributarios), creada por la **Ley 7143/2023**, que absorbió a la ex-SET [F10].
- Técnico [F70 `stdnum.py.ruc`]: personas (nacionales o extranjeras) usan su CI más un DV, hasta 9 dígitos en total. Las personas jurídicas usan 8 dígitos desde el 80000000, más el DV.
- **Algoritmo** [F70]: pesos 2, 3, 4… de derecha a izquierda. DV = 11 − r si r > 1; si r es 0 o 1, DV = 0. Las fuentes secundarias dicen que los pesos vuelven a 2 después de 11 («base máxima 11») [F11]. Para cuerpos de 9 dígitos o menos el resultado es el mismo.
- Ejemplos: `80028061-0` [F70, verificado] y `44444401-7` [F11, recalculado aquí: S = 158].
- Documento técnico oficial de la DNIT con el algoritmo: **NO VERIFICADO**.

**Ley de datos personales:** **Ley 7593/2025** de Protección de Datos Personales, promulgada el 27-11-2025. Prevé reglamentación y un período de transición; la vigencia plena se espera para 2027. Crea la Agencia Nacional de Protección de Datos Personales [F12].

### 3.5 Bolivia (BO)

**CI — Cédula de Identidad.** El SEGIP es el único emisor (Ley 145) [F13].
- Hay unos 400.000 números duplicados. Para distinguirlos existe un **complemento** alfanumérico que se agrega al número. El DS 4861/2023 incluye el «código complemento, en los casos que corresponda» [F13, F14].
- El formato del complemento (¿2 caracteres?) y la longitud del número: **NO VERIFICADO**.
- Sin DV conocido.
- La extensión del departamento (LP, CB, SC…): stdnum para JS la exige como parte del número [F72 `bo/ci`]. Si forma parte del número o es solo el lugar de expedición: **NO VERIFICADO**.

**NIT — Número de Identificación Tributaria (Servicio de Impuestos Nacionales).** Estructura **NO VERIFICADA**: solo hay una guía comercial que dice que deriva de la CI.

**Datos personales:** no hay ley general. Está la acción de protección de privacidad del art. 130 de la Constitución, y AGETIC presentó un anteproyecto en 2024 [F15].

### 3.6 Perú (PE)

**DNI — Documento Nacional de Identidad (RENIEC, Ley 26497).** Desde la Ley 32237 (2025), el DNI de un adulto vale 10 años; el número no cambia [F16].
- Técnico [F70 `stdnum.pe.cui`]: 8 dígitos (el CUI). En el documento figura además un **carácter de verificación** que no forma parte del número: puede ser un dígito o una letra.
- **Algoritmo** [F70]: pesos `3,2,7,6,5,4,3,2`; r = S mod 11. Dígito = `"65432110987"[r]`; letra = `"KJIHGFEDCBA"[r]`. Valen los dos.
- Ejemplo: `10117410-2` [F70, verificado]. RENIEC no publica el algoritmo, según la prensa [F17].

**CE — Carné de Extranjería (Migraciones).** stdnum para JS lo valida como 9 dígitos, sin fuente → **NO VERIFICADO**.

**RUC — Registro Único de Contribuyentes (SUNAT; D. Leg. 943; RS 210-2004/SUNAT).** Normativo [F18, OCDE PE]: 11 dígitos.
- `10` + DNI + DV para personas con DNI.
- `15` + número aleatorio + DV para personas con otro documento.
- `20` + número aleatorio + DV para personas jurídicas.
- stdnum también acepta el prefijo `17`.
- **Algoritmo** [F70 `stdnum.pe.ruc`]: pesos `5,4,3,2,7,6,5,4,3,2`. DV = (11 − (S mod 11)) mod 10, o sea, r = 0 → 1 y r = 1 → 0.
- Ejemplo: `20512333797` [F70, verificado].

**Ley de datos personales:** Ley 29733 y su nuevo reglamento, el DS 016-2024-JUS (publicado el 30-11-2024) [F19].

### 3.7 Ecuador (EC)

**Cédula de identidad.** La emite la Dirección General de Registro Civil, Identificación y Cedulación, según la Ley Orgánica de Gestión de la Identidad y Datos Civiles. Es obligatoria desde los 18 años para ecuatorianos y para extranjeros residentes [F20, OCDE EC].
- Técnico [F70 `stdnum.ec.ci`]: 10 dígitos. Los 2 primeros son la provincia (01 a 24, 30 o 50); el tercero es menor que 7.
- **Algoritmo:** coeficientes 2,1,2,1… con «pliegue» (si el producto pasa de 9 se le resta 9). Para 10 dígitos esto es **exactamente Luhn**: se comprobó en 20.000 casos.
- Ejemplo: `171430710-3` [F70, verificado].

**RUC — Registro Único de Contribuyentes (SRI).** Normativo [F20]: 13 dígitos, sin letras (Reglamento de la Ley del RUC, art. 3).
- Personas: los 10 dígitos de la cédula + `001`.
- Sociedades privadas y extranjeros no residentes: provincia (2) + `9` + 6 consecutivos + DV + `001`.
- Entidades públicas: provincia + `6` + 5 consecutivos + DV + `0` + `001`.
- **Algoritmos** [F70 `stdnum.ec.ruc`]:
  - Privadas: pesos `4,3,2,7,6,5,4,3,2` sobre 9 dígitos. DV = (−S) mod 11; si da 10, el número no es válido.
  - Públicas: pesos `3,2,7,6,5,4,3,2` sobre 8 dígitos, misma regla.
  - Personas: Luhn sobre la cédula, y el establecimiento no puede ser `000`.
- Ejemplo: `1792060346-001` [F70, verificado].

**Ley de datos personales:** Ley Orgánica de Protección de Datos Personales, R.O. Suplemento 459 del 26-05-2021 [F21].

### 3.8 Colombia (CO)

**CC — Cédula de Ciudadanía (Registraduría Nacional del Estado Civil).**
- Normativo: el NUIP tiene 10 dígitos y empieza en 1.000.000.000. Quienes ya tenían cédula conservaron su número como NUIP (Resolución 3571 de 2003) [F22].
- Los menores tienen tarjeta de identidad o registro civil con el mismo NUIP.
- Sin DV. Las cédulas anteriores a 2003 tienen menos dígitos (6 a 8 de forma habitual, según un proveedor comercial; **NO VERIFICADO**).

**CE / PEP / PPT (Migración Colombia):** formatos **NO VERIFICADOS**.

**NIT — Número de Identificación Tributaria (DIAN; Estatuto Tributario art. 555-1; DV según la Orden Administrativa 4 de 1989).** Normativo [F23, OCDE CO]:
- Personas jurídicas: 9 dígitos (800000000 a 899999999, y desde 900000000 en adelante) + DV.
- Personas con cédula: el número de la cédula + DV.
- Tarjeta de identidad o registro civil anteriores al NUIP: rango 700000001 a 799999999.
- Extranjeros: rango 600000001 a 799999999.
- La DIAN aclara que el DV **«no se considera número integrante del NIT»**.
- **Algoritmo** [F70 `stdnum.co.nit`; F24]: pesos `3,7,13,17,19,23,29,37,41,43,47,53,59,67,71` de derecha a izquierda. r = S mod 11. DV = r si r es 0 o 1; si no, DV = 11 − r.
- Ejemplos: `890.903.938-8` [F24, recalculado: S = 1081] y `213.123.432-1` [F70, verificado].

**Ley de datos personales:** Ley Estatutaria 1581 de 2012 (D.O. 48587), reglamentada en parte por el Decreto 1377 de 2013 [F25].

### 3.9 Venezuela (VE)

**Cédula de identidad (SAIME).** La Ley Orgánica de Identificación (G.O. 38.458, 14-06-2006), art. 4, dice que el número se asigna de por vida [F26]. Una reforma de 2014 (G.O. 6.155 Ext.) se cita solo en fuentes no oficiales: **NO VERIFICADO**.
- Formato habitual: `V` (venezolano) o `E` (extranjero) + número. Longitud máxima de 8 dígitos y ausencia de DV: **NO VERIFICADO**.

**RIF — Registro de Información Fiscal (SENIAT).** Habitual [F27]: 10 caracteres, letra + 8 dígitos + DV. Para la letra V, los 8 dígitos son la cédula.
- Letras que acepta stdnum: V (venezolano), E (extranjero), J (jurídica), P (pasaporte) y G (gobierno). Otras letras (por ejemplo, C): **NO VERIFICADO**.
- **Algoritmo** [F70 `stdnum.ve.rif`]: la letra vale V = 1, E = 2, J = 3, P = 4, G = 5 y pesa 4; los dígitos llevan pesos `3,2,7,6,5,4,3,2`. r = S mod 11. DV = 0 si r es 0 o 1; si no, DV = 11 − r.
- Ejemplo: `V-11470283-4` [F70, verificado].
- La Providencia SNAT/2026/00080 (G.O. 43.435, 12-08-2026) reemplaza la regulación del RIF y **elimina su vencimiento** [F28].

**Datos personales:** no hay ley especial [F29]. El art. 28 de la Constitución (hábeas data) se cita en la literatura, pero aquí **NO VERIFICADO**.

### 3.10 México (MX)

**CURP — Clave Única de Registro de Población (RENAPO, Secretaría de Gobernación).** Normativo (Instructivo normativo para la asignación de la CURP, 2018) [F30]: 18 posiciones.
- Posiciones 1 a 4: letras del nombre.
- 5 a 10: fecha de nacimiento AAMMDD.
- 11: sexo, H o M.
- 12 y 13: entidad de nacimiento.
- 14 a 16: consonantes internas.
- 17: diferenciador de homonimia y siglo: **0-9 hasta 1999; A-J desde el año 2000**.
- 18: **dígito verificador «asignado mediante un algoritmo»**, que el instructivo no describe.
- **Algoritmo técnico** [F70 `stdnum.mx.curp`]: alfabeto `0-9 A-N Ñ O-Z` con valores de 0 a 36 (stdnum escribe `&` en el lugar de la Ñ); pesos 18 a 2 sobre las primeras 17 posiciones; DV = (10 − (S mod 10)) mod 10.
- Validaciones de componentes [F70]: lista de entidades válidas, fecha real y lista de palabras inconvenientes en las posiciones 1 a 4.
- Ejemplo: `BOXW310820HNERXN09` [F70, verificado].

**RFC — Registro Federal de Contribuyentes (SAT; Código Fiscal de la Federación, art. 27).** Normativo [F31, OCDE MX]:
- Persona física: **13 caracteres** = 4 letras + 6 dígitos + 3 alfanuméricos.
- Persona moral: **12 caracteres** = 3 letras + 6 dígitos + 3.
- Los adultos sin actividad económica también deben inscribirse.
- **DV técnico** [F70 `stdnum.mx.rfc`]: alfabeto `0-9 A-N & O-Z ␠ Ñ`; el RFC moral se rellena a la izquierda con un espacio hasta 12 caracteres; pesos 13 a 2; DV = alfabeto[(11 − (S mod 11)) mod 11], o sea, 10 → `A`.
- **Alrededor del 1,5 % de los RFC en uso tienen un DV inválido**, así que stdnum no controla el DV por defecto [F70].
- La homoclave (los 2 primeros caracteres de los 3 finales) sale del nombre completo y **no se puede verificar sin él**.
- Ejemplos: `GODE561231GR8` y `MAB9307148T4` [F70, verificados con control de DV].

**Leyes de datos personales:** Ley General de Protección de Datos Personales en Posesión de Sujetos Obligados (LGPDPPSO, DOF 20-03-2025; obliga a los municipios) y Ley Federal de Protección de Datos Personales en Posesión de los Particulares (DOF 20-03-2025) [F32]. Las leyes estatales: **NO VERIFICADO**.

### 3.11 Guatemala (GT)

**DPI — Documento Personal de Identificación / CUI — Código Único de Identificación (RENAP).** Normativo [F33]: Decreto 90-2005, art. 4, reformado por el Decreto 39-2010, art. 1.
- El CUI se asigna al inscribir el nacimiento y **es invariable**.
- 13 dígitos: **8 asignados + 1 dígito verificador + 2 del departamento de nacimiento + 2 del municipio de nacimiento**.
- En inscripciones consulares, naturalizaciones o residentes extranjeros, las casillas de departamento y municipio se usan según lo que disponga el Directorio del RENAP.
- **Algoritmo del DV:** RENAP no lo publica [F34].
  - Técnico [F72 `gt/cui`]: pesos `2,3,4,5,6,7,8,9` sobre los 8 primeros dígitos, de izquierda a derecha; DV = (S mod 11) mod 10. También controla que el municipio exista en su departamento.
  - **Cálculo propio:** ese DV coincide con el DV del NIT (ver abajo) de los mismos 8 dígitos en todos los casos, salvo cuando el resto es 10 (alrededor del 9 % de los casos). Eso es coherente con que hoy el NIT sea igual a los 9 primeros dígitos del CUI. Qué hace RENAP cuando el resto es 10: **NO VERIFICADO**.

**NIT — Número de Identificación Tributaria (SAT).** Técnico [F70 `stdnum.gt.nit`, que cita las reglas FEL de la SAT, p. 58; ese PDF dio 403 y no se pudo abrir]:
- 2 a 12 caracteres; el último es el DV (dígito o K); se quitan los ceros a la izquierda.
- **Algoritmo:** pesos 2, 3, 4… de derecha a izquierda, sin tope. DV = (−S) mod 11; 10 → `K`.
- Ejemplos: `576937-K` y `7108-0` [F70, verificados].
- **Unificación CUI-NIT** (Resolución SAT-DSI-393-2025): las personas individuales reciben como NIT **los primeros 9 dígitos del CUI**. No se aplica a empresas [F35].

**Datos personales:** no hay ley general. La Ley de Acceso a la Información Pública (Decreto 57-2008) regula los datos personales y sensibles. En el Congreso están las iniciativas 6105 y 6464 [F36].

### 3.12 Honduras (HN)

**DNI — Documento Nacional de Identificación (Registro Nacional de las Personas, RNP).** Nuevo DNI desde 2021.
- 13 dígitos: código geográfico + año de inscripción + número de inscripción [F37, artículo académico].
- Que el código geográfico sea departamento (2) + municipio (2), y el número de 5 dígitos: habitual, **NO VERIFICADO**. Sin DV conocido.

**RTN — Registro Tributario Nacional (SAR).** 14 dígitos. Para personas naturales es el DNI más un dígito que asigna el sistema [F38, prensa].
- Cómo se calcula ese dígito: **NO VERIFICADO**.
- Estructura del RTN de personas jurídicas: **NO VERIFICADO**.

**Datos personales:** no se verificó una ley general vigente. Hay un anteproyecto del IAIP de 2024 [F39]. Un «Decreto 25-2013» citado por ICANNWiki: **NO VERIFICADO**. Que el hábeas data esté en la Ley de Transparencia y Acceso a la Información Pública (Decreto 170-2006): **NO VERIFICADO**.

### 3.13 El Salvador (SV)

**DUI — Documento Único de Identidad (RNPN; Ley Especial Reguladora de la Emisión del DUI, D.L. 581 de 2001).** Es el documento oficial, suficiente y necesario para identificar a una persona salvadoreña [F40].
- Formato habitual: 8 dígitos + DV (`00000000-0`).
- **Algoritmo NO VERIFICADO oficialmente:** según fuentes comunitarias, pesos 9 a 2 y DV = (10 − (S mod 10)) mod 10 [F41]. Un módulo de Odoo solo dice «módulo 10» [F42].
- No se encontró un DUI válido de ejemplo en ninguna fuente.

**NIT (Ministerio de Hacienda).** Técnico [F70 `stdnum.sv.nit`]: 14 dígitos, `XXXX-XXXXXX-XXX-X` = municipio + fecha DDMMAA + correlativo + DV. Empieza con 0 o 1 (salvadoreños) o con 9 (extranjeros).
- **Algoritmo condicional:**
  - Correlativo (posiciones 11 a 13) ≤ 100: pesos 14 a 2; DV = (S mod 11) mod 10.
  - Correlativo > 100: pesos `2,7,6,5,4,3,2,7,6,5,4,3,2`; DV = ((−S) mod 11) mod 10.
- Ejemplo: `0614-050707-104-8` [F70, verificado].
- **Homologación:** el Decreto 203-2021 reformó la Ley del Registro y Control Especial de Contribuyentes al Fisco. Para los **salvadoreños mayores de edad, el NIT es el número del DUI**; desde el 1-07-2022 los trámites se hacen con el DUI. Los menores, los extranjeros y las personas jurídicas conservan su NIT [F43, F44].

**Ley de datos personales:** Ley para la Protección de Datos Personales, Decreto Legislativo 144, D.O. del 15-11-2024, Tomo 445 [F45].

### 3.14 Nicaragua (NI)

**Cédula de identidad ciudadana (Consejo Supremo Electoral; Ley 152 de Identificación Ciudadana, 1993).** Un formato nuevo rige desde el 21-02-2026 [F46].
- **Estructura del número NO VERIFICADA.** La forma habitual sería código de municipio (3) + fecha DDMMAA (6) + consecutivo (4) + letra (ej. `001-010180-0001A`), pero no se encontró fuente.
- Algoritmo de la letra: **NO VERIFICADO**.
- La Ley 1241 de 2025 sobre identificación y su posible derogación: **NO VERIFICADO**.

**RUC (Dirección General de Ingresos).** Estructura **NO VERIFICADA**: una fuente de baja calidad habla de 14 caracteres, y tampoco se confirmó el prefijo «J» de las personas jurídicas.

**Ley de datos personales:** Ley 787 (La Gaceta N° 61, 29-03-2012) y su reglamento, el Decreto 36-2012 [F47].

### 3.15 Costa Rica (CR)

Normativo [F48, OCDE CR]:

| Documento | Emisor | Estructura | Notas |
|---|---|---|---|
| Cédula de identidad (persona física) | TSE | `X-XXXX-XXXX`, 9 números | El guion no es obligatorio |
| Cédula jurídica | Registro Nacional | `X-XXX-XXXXXX`, 10 números | |
| DIMEX (extranjeros residentes) | Dirección General de Migración y Extranjería | 11 o 12 números | |
| NITE (persona física) | Hacienda | `3-120-XXXXXX`, 10 números | Para quien no tiene DIMEX |
| NITE (entidad sin personalidad jurídica) | Hacienda | `3-130-XXXXXX`, 10 números | |

- Técnico [F70 `stdnum.cr.cpf`, `cpj`, `cr`]:
  - Cédula física = provincia-tomo-asiento. Es habitual omitir los ceros a la izquierda de cada parte (`1-613-584` equivale a `01-0613-0584`), así que **la normalización tiene que rellenar cada parte antes de quitar los guiones**.
  - Cédula jurídica: el primer dígito es la clase (2 a 5) y le sigue un tipo de 3 dígitos tomado de una lista cerrada.
  - DIMEX: empieza con 1.
  - **Ninguno de estos documentos tiene DV.**
- Ejemplo de cédula jurídica: `3-101-999999` [F70].

**Ley de datos personales:** Ley 8968 de Protección de la Persona frente al tratamiento de sus datos personales, con su reglamento (DE 37554-JP); la autoridad es PRODHAB [F49].

### 3.16 Panamá (PA)

**Cédula de Identidad Personal (Tribunal Electoral, Dirección Nacional de Cedulación; Decreto 53 de 1958, art. 9).** Normativo [F50, OCDE PA]:
- Nacidos en Panamá: provincia (1 a 13) + tomo + asiento, por ejemplo `8-926-1601`.
- Panameños nacidos en el extranjero: `PE-5-687`.
- Naturalizados: `N-19-473`.
- Extranjeros domiciliados: `E-8-74258`.
- El documento técnico de la DGI agrega `PI` (panameño indígena) y `AV` («antes de la vigencia») [F51].
- **Longitud variable** («hasta 5, 6, 7, 8 o más caracteres»: `[1-2]-[1-4]-[1-4]`). **Los guiones separan partes de largo variable y no se pueden quitar sin perder información.** Sin DV.

**RUC (DGI; Ley 76 de 1976; Decreto Ejecutivo 847 de 2014).** Normativo [F50]:
- Persona natural: la cédula + DV.
- Persona jurídica: el número del Registro Público. Las sociedades anteriores a 1985 tienen formato viejo con letras y puntos, de los que se usan solo los dígitos. **Desde el 24-10-2014** el formato es `FolioReal-2-AAAA` (sociedades comerciales) o `FolioReal-3-AAAA` (no comerciales).
- **NT** (número tributario) para extranjeros sin cédula y entidades sin personalidad jurídica.
- Para el CRS los guiones son obligatorios y el DV no se exige.
- El **DV tiene 2 dígitos.**

**Algoritmo del DV** (documento DGI «Sistema de Información Tributaria — Algoritmo para el cálculo del Dígito Verificador (DV)», Versión 201805; copia publicada en GitHub, no se encontró en el sitio de la DGI) [F51]:
1. Se arma una cadena de 20 posiciones, alineada a la derecha y rellenada con ceros, según el tipo de RUC.
2. Las letras se reemplazan: `N` → 5 (persona natural); `NT` → 4 y 3; `E` → 5; `PE` → 7 y 5; `PI` → 7 y 9; `AV` → 1 y 5.
3. En los RUC jurídicos antiguos (posición 4 = 0, posición 5 = 0, posición 6 < 5) se aplica una tabla de referencia cruzada a las posiciones 6 y 7, y el peso 12 se reemplaza por 11.
4. DV1: suma de dígito × peso, con pesos 2, 3, 4… de derecha a izquierda; r = S mod 11; DV1 = 0 si r es 0 o 1; si no, DV1 = 11 − r.
5. DV2: el mismo cálculo sobre las 21 posiciones (las 20 más DV1).

**Contradicción sin resolver:**
- La implementación pública `panama-ruc-dv-calculator` 1.0.4 da los DV de sus 2 ejemplos y el del ejemplo NT de la OCDE (`3-NT-3-33` → 45).
- **No** da los otros 4 ejemplos de la OCDE: `8-100-678` → 90 (calcula 63), `4789-321-1515` → 85 (45), `155986022-2-2019` → 12 (95) y `26631254-3-2020` → 78 (35).
- Puede ser que los ejemplos de la OCDE sean ilustrativos o que la implementación esté incompleta (por ejemplo, en los RUC de Folio Real). **NO VERIFICADO**. Para resolverlo hay que contrastar con la consulta «Dígito Verificador» de e-Tax 2.0 de la DGI.

**Ley de datos personales:** Ley 81 de 2019 (G.O. del 29-03-2019) y su reglamento, el Decreto Ejecutivo 285 de 2021 [F52].

### 3.17 Cuba (CU)

**Carné de identidad, número de identidad.** Técnico [F70 `stdnum.cu.ni`, que cita postdata.club]: 11 dígitos.
- Posiciones 1 a 6: fecha AAMMDD.
- Posición 7: siglo (9 → 1800; 0 a 5 → 1900; 6 a 8 → 2000).
- Posición 10: sexo (par = masculino, impar = femenino).
- stdnum valida solo la longitud y la fecha. Que el dígito 11 sea un DV (lo afirma una guía comercial): **NO VERIFICADO**, sin algoritmo.
- Emisor (MININT): **NO VERIFICADO** en fuente oficial.
- Un proyecto de «Ley del Sistema de Identidad Personal y Domicilio» crearía un número de identidad permanente; su estado (aprobada o no): **NO VERIFICADO** [F53].

**NIT de la ONAT (personas jurídicas y trabajadores por cuenta propia):** formato **NO VERIFICADO**.

**Ley de datos personales:** Ley 149 «De Protección de Datos Personales» (G.O. Ordinaria N° 90, 25-08-2022). La controla el Ministerio de Justicia y está vigente desde febrero de 2023 [F54].

### 3.18 República Dominicana (DO)

**Cédula de Identidad y Electoral (Junta Central Electoral; Ley 8-92).** 11 dígitos; también se usa como identificador tributario de la persona y como número de licencia de conducir [F55].
- Se escribe `###-#######-#` [F70].
- **Algoritmo técnico** [F70 `stdnum.do.cedula`]: Luhn sobre los 11 dígitos, **más una lista de unas 578 cédulas emitidas que no cumplen el DV y aun así son válidas**.
- Ejemplo: `001-1391820-5` [F70, verificado].
- Nueva cédula desde abril de 2026 [F55]: si cambia el número, **NO VERIFICADO**.

**RNC — Registro Nacional de Contribuyentes (DGII).** Personas jurídicas: 9 dígitos, `#-##-#####-#`. Las personas físicas dominicanas usan la cédula (fuentes secundarias) [F56].
- **Algoritmo** [F70 `stdnum.do.rnc`]: pesos `7,9,8,6,5,4,3,2`; r = S mod 11; DV = ((10 − r) mod 9) + 1. También tiene una lista de excepciones históricas.
- Ejemplo: `1-01-85004-3` [F70, verificado].

**Ley de datos personales:** Ley 172-13 sobre protección integral de los datos personales (G.O. 10737) [F57].

### 3.19 Anexo: España (ES)

Normativo [F58, OCDE ES]: el NIF tiene 9 caracteres.
- Personas españolas: DNI = 8 dígitos + letra.
- Españoles sin DNI: `K` (residentes menores de 14 años) o `L` (no residentes) + 7 + letra.
- Extranjeros: NIE = `X`, `Y` o `Z` + 7 + letra. Sin NIE: `M` + 7 + letra (transitorio).
- Entidades: letra de forma jurídica (A, B, C, D, E, F, G, H, J, P, Q, S, U, V; N extranjeras; W establecimientos permanentes) + 7 dígitos + carácter de control.

**Algoritmos técnicos** [F70 `stdnum.es.dni`, `nie`, `cif`]:
- DNI: letra = `"TRWAGMYFPDXBNJZSQVHLCKE"`[número mod 23].
- NIE: X, Y o Z se reemplaza por 0, 1 o 2 y se aplica el algoritmo del DNI.
- Entidades: Luhn sobre los 7 dígitos; el control es el dígito, o la letra `"JABCDEFGHI"`[dígito].

**Datos personales:** RGPD y Ley Orgánica 3/2018 (LOPDGDD) [F59].

---

## 4. Propuesta de modelado

### 4.1 Principios

- **El catálogo es global, no es por municipio.** Lo administra el super administrador, igual que los catálogos geográficos del plan (§7). Cada municipio solo elige qué tipos ofrece por defecto, y lo hace por su país.
- **Código** = algoritmos genéricos, validadores de componentes, primitivas de normalización y el armado de la máscara. **Datos** = qué algoritmo usa cada tipo, con qué parámetros, longitudes, regex, máscara, etiquetas, ejemplos, excepciones, relaciones entre tipos y fuente normativa.
- **El número se guarda siempre como texto normalizado**, nunca como entero: hay ceros a la izquierda con significado (Ecuador, Costa Rica, Uruguay, El Salvador), letras y guiones con significado (Panamá).
- **Toda validación del backend sale del catálogo.** El frontend puede replicar los mismos 3 o 4 algoritmos para dar respuesta instantánea, pero el backend decide. Los ejemplos del catálogo sirven como vectores de prueba para asegurar que los dos den lo mismo.

### 4.2 Tabla `tipo_documento` (catálogo)

| Campo | Tipo | Para qué / caso que lo justifica |
|---|---|---|
| `id_tipo_documento` | PK | — |
| `pais` | `CHAR(2)` NULL | ISO 3166-1 alfa-2. **NULL** = tipo genérico internacional (PASAPORTE, OTRO): en ese caso el país va en el documento de la persona (país emisor). |
| `codigo` | `VARCHAR(20)` | UNIQUE (`pais`, `codigo`): `DNI`, `CUIL`, `CUIT`, `RUN`, `RUT`, `CI`, `NIE`, `RUC`, `NIT`, `CC`, `RIF`, `CURP`, `RFC`, `CUI`, `DUI`, `RTN`, `CEDULA`, `DIMEX`, `CED_JURIDICA`, `NITE`, `RNC`… |
| `etiqueta` | `VARCHAR(60)` | Lo que ve el usuario («DNI», «Cédula de identidad», «RUT»). Reemplaza los textos fijos «DNI» de la interfaz (plan §7, F5b). |
| `nombre_oficial`, `sigla` | texto | «Clave Única de Identificación Tributaria», «CUIT». |
| `organismo_emisor` | texto | RENAPER, AFIP/ARCA, SII, RENAP… |
| `aplica_a` | `persona` \| `empresa` \| `ambos` | El CUIT de Argentina y el RUT de Uruguay son `ambos`; el DNI es `persona`; la cédula jurídica de Costa Rica es `empresa`. |
| `es_identidad` | bool | Sirve para acreditar identidad (DNI, CI, CURP). El RFC y el RTN no. |
| `es_fiscal` | bool | Identificador tributario o laboral. |
| `ambito` | `nacional` \| `extranjero` \| `ambos` | DIMEX, CE y NIE son de extranjeros; la cédula E de Venezuela y la E- de Panamá son variantes. |
| `edad_minima` | int NULL | DUI de El Salvador (18); cédula de Ecuador (18). Para guiar el formulario de un menor, no para rechazar. |
| `normalizacion` | JSONB | Ver §4.4. |
| `longitud_min`, `longitud_max` | int | Sobre el valor normalizado. |
| `patron` | text (regex anclada) | Sobre el valor normalizado. Ej.: CUIT `^(20\|23\|24\|27\|30\|33\|34)\d{9}$`; CURP `^[A-Z]{4}\d{6}[HM][A-Z]{5}[0-9A-Z]\d$`. |
| `mascara` | text NULL | `#` dígito, `A` letra, `X` alfanumérico; el resto es literal. Ej.: `##-########-#`. |
| `mascara_alineacion` | `izq` \| `der` | Si es `der`, la máscara se llena desde la derecha para largos variables (RUT `##.###.###-#` con 7 u 8 dígitos; DNI `##.###.###`). |
| `algoritmo` | `VARCHAR(30)` | Clave de un algoritmo registrado en código (§5): `ninguno`, `ponderado`, `luhn`, `compuesto`, `pa_ruc_dv`. |
| `algoritmo_params` | JSONB | Se valida contra el JSON Schema del algoritmo al guardar. |
| `nivel_dv` | `error` \| `advertencia` \| `no_verificar` | El DV del **RFC** debe ser `advertencia` (≈1,5 % de RFC en uso con DV inválido). El DV de la **cédula de República Dominicana** es `error`, con lista de excepciones. |
| `componentes` | JSONB | Validaciones estructurales adicionales (§5.3): fecha embebida (CURP, NIT de El Salvador, CI de Cuba), catálogo posicional (entidad de la CURP, provincia de Ecuador, departamento y municipio del CUI). |
| `contiene_a` | JSONB NULL | Relación con otro tipo: `{"codigo": "DNI", "desde": 2, "largo": 8}` para el CUIL. Ver §4.5. |
| `ejemplos_validos` | `TEXT[]` | Vectores de prueba con su fuente. **Sin al menos uno, el tipo no se puede activar.** |
| `ejemplos_invalidos` | `TEXT[]` | Al menos uno con el DV alterado, para probar que el algoritmo rechaza. |
| `vigente_desde`, `vigente_hasta` | date NULL | Documentos que dejan de emitirse o cambian (NIT de persona de El Salvador desde 2022; RUC jurídico de Panamá antes de 2014). |
| `fuente_normativa` | text | Norma y URL. |
| `estado_verificacion` | `normativa` \| `tecnica` \| `no_verificado` | La interfaz del super administrador lo muestra; un tipo `no_verificado` puede usarse, pero solo con `nivel_dv = advertencia`. |
| `orden`, `es_principal` | — | Orden en los selects; tipo que se propone por defecto para persona o empresa en ese país. |
| campos §10 | — | `activo`, `fecha_alta`, `fecha_modificacion`, `id_usuario_alta`, `id_usuario_modificacion`. Tabla nueva con RLS habilitado. |

Tabla aparte **`tipo_documento_excepcion`** (`id_tipo_documento`, `valor_normalizado`, `motivo`, `fuente`): números válidos aunque no cumplan el DV. Cubre las ~578 cédulas de República Dominicana y los RNC históricos. Es una tabla y no un array porque se mantiene y se audita fila por fila.

### 4.3 Documento de la persona y de la empresa

Lo que el plan ya decidió (país, tipo, número) se puede bajar así:

- `ciudadano_documento` / `empresa_documento`: `id`, FK a la entidad, `pais` (país emisor; obligatorio aunque el tipo sea genérico), `id_tipo_documento`, `numero` (normalizado), `complemento` (Bolivia), `es_principal`, `verificado_por` (`formato` \| `padron_externo` \| `manual`), `fecha_vencimiento` NULL, `activo`, más los campos §10.
- Índice **UNIQUE parcial** (`id_tipo_documento`, `numero`, `coalesce(complemento,'')`) WHERE `activo`. En Bolivia la unicidad la da el número **con** el complemento.
- Las columnas actuales de ZARIS (`ciudadanos.doc_tipo`/`doc_nro`/`cuil`, `empresas.cuit`) pueden quedar como copia del documento principal durante la transición. Argentina se migra como DNI principal + CUIL secundario; el CUIT de la empresa queda como principal.

### 4.4 Normalización: primitivas en código, configuración en datos

```json
{
  "quitar": " .-/",              // caracteres a eliminar (no aplica si se usan "partes")
  "mayusculas": true,
  "quitar_prefijo_pais": ["UY"],  // stdnum acepta "UY", "CL" y "SV" pegados al número
  "ceros_izquierda": "conservar", // conservar | quitar (NIT de Guatemala) | rellenar (largo)
  "rellenar_a": null,             // ej. 7 para la CI de Uruguay de 6 dígitos
  "partes": null                  // ej. Costa Rica: {"separador": "-", "rellenos": [2,4,4]} → se rellena cada parte y después se une
}
```

Panamá es el caso extremo. El valor normalizado **conserva los guiones**: `8-926-1601`, `PE-5-687`, `E-8-74258`, `3-NT-3-33`. El patrón se escribe sobre esa forma, por ejemplo `^(\d{1,2}(AV|PI)?|E|N|PE)-\d{1,4}-\d{1,6}$`. Ese patrón es tentativo y queda **NO VERIFICADO** para todas las combinaciones.

### 4.5 Relaciones entre tipos (`contiene_a`)

Para no pedir dos veces el mismo dato y para cruzar consistencia:

| País | Tipo derivado | Regla |
|---|---|---|
| AR | CUIL/CUIT (persona) | posiciones 3 a 10 = DNI |
| CL | RUT | = RUN |
| PY | RUC (persona) | = CI + DV |
| PE | RUC 10 | posiciones 3 a 10 = DNI |
| EC | RUC (persona) | posiciones 1 a 10 = cédula; sufijo `001` |
| CO | NIT (persona) | = CC + DV (el DV no integra el NIT) |
| VE | RIF V/E | posiciones 2 a 9 = cédula |
| GT | NIT (persona, desde 2025) | = CUI[1..9] |
| SV | NIT (persona adulta, desde 2022) | = DUI |
| HN | RTN (persona) | DNI + 1 dígito (NO VERIFICADO) |
| PA | RUC (persona) | = cédula; DV aparte |
| DO | RNC (persona) | = cédula |

Uso: cuando se carga el DNI, el formulario puede proponer el CUIL. Al guardar, el backend controla que el CUIL contenga ese DNI, como **advertencia**, no como error, porque hay excepciones como el prefijo 23 o los números asignados antes de la regla.

---

## 5. Algoritmos de verificación: el conjunto mínimo

### 5.1 `ponderado` (cubre 17 esquemas de 12 países, más España)

**Definición.** Sea V el valor normalizado.

1. `cuerpo` = la porción de V que entra en la suma. Por defecto es todo menos los últimos `largo_dv` caracteres; `dv` = esos últimos (por defecto, 1).
2. Si hay `relleno_izq: {car, largo}`, se rellena el cuerpo por la izquierda hasta `largo`.
3. Cada carácter c se convierte en un valor: `alfabeto` como cadena (el valor es la posición) o como mapa `{car: valor}`. Por defecto, `"0123456789"`.
4. Pesos:
   - `pesos` (lista) con `sentido` (`izq`: el 1.er peso va al 1.er carácter; `der`: el 1.er peso va al último carácter) y `ciclico` (repetir la lista); o bien
   - `progresivo_desde: n`: pesos n, n+1, n+2… desde el `sentido` indicado, con `progresivo_hasta: m` opcional (después de m vuelve a n).
5. S = Σ valor × peso; r = S mod `modulo`.
6. DV esperado = `tabla[r]`, donde `tabla` tiene largo `modulo`. El carácter `-` en la tabla significa «ese resto no puede darse: número inválido». `tablas_alternativas` permite aceptar cualquiera de varias tablas (DNI de Perú: dígito o letra). Con `dv_opcional: true` también se acepta el número sin DV (DNI de Perú de 8 dígitos).

**Parámetros por esquema** (todos contrastados, §5.4):

| Esquema | alfabeto | pesos / sentido | módulo | tabla (índice = resto) |
|---|---|---|---|---|
| AR CUIT/CUIL (compatible con ZARIS hoy) | dígitos | `5,4,3,2,7,6,5,4,3,2` izq | 11 | `09987654321` (estricto: `0-987654321`) |
| UY RUT | dígitos | `4,3,2,9,8,7,6,5,4,3,2` izq | 11 | `0-987654321` |
| UY CI | dígitos (`rellenar_a` 7) | `2,9,8,7,6,3,4` izq | 10 | `0987654321` |
| CL RUN/RUT | dígitos | `2,3,4,5,6,7` der, cíclico | 11 | `0K987654321` |
| PY RUC | dígitos | progresivo desde 2, der (hasta 11) | 11 | `00987654321` |
| PE RUC | dígitos | `5,4,3,2,7,6,5,4,3,2` izq | 11 | `10987654321` |
| PE DNI (carácter de control) | dígitos | `3,2,7,6,5,4,3,2` izq | 11 | `65432110987` o `KJIHGFEDCBA`; opcional |
| EC RUC privada (9 dígitos) | dígitos | `4,3,2,7,6,5,4,3,2` izq | 11 | `0-987654321` |
| EC RUC pública (8 dígitos) | dígitos | `3,2,7,6,5,4,3,2` izq | 11 | `0-987654321` |
| CO NIT | dígitos | `3,7,13,17,19,23,29,37,41,43,47,53,59,67,71` der | 11 | `01987654321` |
| VE RIF | `{0-9: valor, V:1, E:2, J:3, P:4, G:5}` | `4,3,2,7,6,5,4,3,2` izq (letra incluida) | 11 | `00987654321` |
| MX CURP | `0123456789ABCDEFGHIJKLMNÑOPQRSTUVWXYZ` | `18…2` izq | 10 | `0987654321` |
| MX RFC | `0123456789ABCDEFGHIJKLMN&OPQRSTUVWXYZ␠Ñ`, `relleno_izq` (␠, 12) | `13…2` izq | 11 | `0A987654321` |
| GT NIT | dígitos | progresivo desde 2, der | 11 | `0K987654321` |
| GT CUI (técnico) | dígitos (cuerpo = posiciones 1 a 8; dv = posición 9) | `2,3,4,5,6,7,8,9` izq | 11 | `01234567890` |
| SV NIT, correlativo ≤ 100 | dígitos | `14…2` izq | 11 | `01234567890` |
| SV NIT, correlativo > 100 | dígitos | `2,7,6,5,4,3,2,7,6,5,4,3,2` izq | 11 | `00987654321` |
| SV DUI (NO VERIFICADO) | dígitos | `9,8,7,6,5,4,3,2` izq | 10 | `0987654321` |
| DO RNC | dígitos | `7,9,8,6,5,4,3,2` izq | 11 | `21987654321` |
| ES DNI/NIE (anexo) | dígitos (NIE: X→0, Y→1, Z→2) | `10^k mod 23` der | 23 | `TRWAGMYFPDXBNJZSQVHLCKE` |

Dos notas sobre la tabla:

- En la CURP, stdnum usa `&` donde va la Ñ; para la CURP no cambia nada, porque la CURP no lleva Ñ.
- El DNI de España, «número entero mod 23», se expresa como `ponderado` con pesos 10^k mod 23. La equivalencia se probó, pero para que sea legible conviene un alias `resto_entero {modulo, tabla}` que internamente sea lo mismo.

### 5.2 `luhn`

Desde la derecha se duplica uno de cada dos dígitos; si el producto pasa de 9 se le resta 9; se suma todo y la suma tiene que ser múltiplo de 10. Parámetros: `cuerpo` (por defecto, todo) y `alfabeto` (por defecto, dígitos).

Lo usan:
- la cédula de República Dominicana (11 dígitos, con excepciones);
- la cédula de Ecuador (10 dígitos: el algoritmo de coeficientes 2,1… con pliegue equivale a Luhn, comprobado);
- el control de las entidades en España (sobre 7 dígitos, combinado con una tabla de letras: se modela como `compuesto`).

### 5.3 `compuesto` y validadores de componentes

**`compuesto`**: `reglas: [{si: <regex sobre el normalizado>, algoritmo, params}]`. Se aplica la primera regla que coincide; si ninguna coincide, el número es inválido. Casos:

- **RUC de Ecuador:**
  - `^\d{2}[0-5]` → `luhn` sobre las posiciones 1 a 10, más regex de sufijo `(?!000)\d{3}$`.
  - `^\d{2}6` → ponderado público, y si no pasa, natural.
  - `^\d{2}9` → ponderado privado.
  - Hace falta permitir una regla del tipo «una u otra», porque stdnum prueba público y después jurídico.
- **NIT de El Salvador:** `^\d{10}(0\d\d|100)\d$` → esquema viejo; si no, esquema nuevo.
- **NIF de entidades en España:** letra de entidad → dígito o letra de control.

**Validadores de componentes** (código, configurables por datos en `componentes`):
- `fecha {desde, largo, formato: AAMMDD|DDMMAA, siglo: {pos, regla}}`: CURP (siglo por la posición 17), NIT de El Salvador, CI de Cuba.
- `catalogo {desde, largo, valores[] | ref}`: entidades de la CURP, provincias de Ecuador (01 a 24, 30), departamento y municipio del CUI de Guatemala, prefijos del CUIT.
- `distinto_de {desde, largo, valor}`: secuencia del RUT de Uruguay ≠ `000000`; establecimiento del RUC de Ecuador ≠ `000`.
- `lista_negra {desde, largo, valores[]}`: las 4 primeras letras de la CURP y del RFC.

### 5.4 Específico en código: `pa_ruc_dv`

El DV de 2 dígitos de Panamá (§3.16) no se puede parametrizar con sensatez: arma la cadena de 20 posiciones según el tipo de RUC, reemplaza letras, aplica una tabla de referencia cruzada a los RUC antiguos y hace el ajuste del peso 12. Va como función propia, con los ejemplos de la OCDE y de la DGI como vectores de prueba, y **con `nivel_dv = advertencia` hasta resolver la contradicción de los ejemplos**.

### 5.5 Contraste del motor (cómo se verificó)

1. Se escribió un motor de referencia `ponderado` + `luhn` y se comparó contra **python-stdnum 2.2**. Con 20.000 entradas aleatorias por esquema hubo **0 diferencias** en AR CUIT, CL RUT, UY RUT, PY RUC, PE RUC, PE DNI, CO NIT, VE RIF, GT NIT, SV NIT (esquemas viejo y nuevo), DO RNC, MX CURP, MX RFC y ES DNI, y la cédula de Ecuador resultó equivalente a Luhn.
2. Contra **stdnum para JS 1.12.6**, con 20.000 casos por esquema: CI de Uruguay, NIE de Uruguay, CUI de Guatemala y RUC de Ecuador (tercer dígito 9). La biblioteca no rechazó ningún número armado por el motor y no aceptó ningún DV alterado.
3. Se validaron con la biblioteca todos los ejemplos de §3 marcados «verificado».

El motor no prueba que el algoritmo sea el oficial: prueba que la parametrización reproduce **exactamente** a la biblioteca citada.

---

## 6. API: configuración y validación

### 6.1 Validar (lo usan los formularios, las altas públicas y los schemas Pydantic)

`POST /api/v1/documentos/validar`

```json
// Entrada
{ "pais": "AR", "tipo": "CUIT", "valor": "20-26756539-3" }
// o bien { "id_tipo_documento": 3, "valor": "..." }

// Salida 200 (siempre 200 si la entrada está bien formada; la invalidez es un resultado, no un error HTTP)
{
  "valido": true,
  "normalizado": "20267565393",
  "presentacion": "20-26756539-3",
  "tipo": { "pais": "AR", "codigo": "CUIT", "etiqueta": "CUIT" },
  "errores": [],              // [{ "codigo": "LONGITUD"|"FORMATO"|"DV"|"COMPONENTE"|"TIPO_INACTIVO", "mensaje": "..." }]
  "advertencias": [],         // DV de RFC, relación contiene_a que no cuadra, tipo no verificado
  "excepcion": false          // true si se aceptó por la lista de excepciones
}
```

- **No devolver el DV esperado** en la ruta pública: facilita fabricar números válidos. La variante de administración sí lo puede mostrar.
- Ruta pública con rate limit y clave con prefijo (`check_rate_limit(f"docval:{ip}", ...)`, regla de CLAUDE.md §5).
- Lo mismo queda expuesto como servicio interno `validar_documento(pais, codigo, valor)`, que llaman los validadores Pydantic. Ese servicio reemplaza a `_validar_modulo11` y usa el catálogo en caché con TTL, igual que `geo._bbox_municipio`.

`GET /api/v1/documentos/tipos?pais=AR&aplica_a=persona`: catálogo para armar formularios (etiqueta, máscara, longitudes, patrón, `es_principal`). Es público, porque lo necesita el alta del vecino.

### 6.2 Configurar (solo el super administrador)

- `GET /api/v1/admin/documentos/algoritmos`: algoritmos registrados en código y el **JSON Schema de sus parámetros**, para que la interfaz arme el formulario.
- `POST /api/v1/admin/documentos/tipos` y `PUT /api/v1/admin/documentos/tipos/{id}`:
  1. valida `algoritmo_params` contra el schema;
  2. compila el `patron`;
  3. **autoprueba**: todos los `ejemplos_validos` deben validar y todos los `ejemplos_invalidos` deben fallar;
  4. si falla algo → 422 con el detalle por ejemplo;
  5. las bajas son lógicas (`activo = false`).
- `POST /api/v1/admin/documentos/tipos/{id}/probar` (simulación): recibe la configuración propuesta y devuelve (a) el resultado de la autoprueba y (b) **cuántos documentos ya guardados dejarían de validar** con esa configuración, con algunos ejemplos enmascarados. Es obligatorio antes de editar un tipo que ya tiene documentos cargados.
- `POST /api/v1/admin/documentos/tipos/{id}/excepciones`: alta o baja de números de excepción, con motivo y fuente.

### 6.3 Qué es código y qué es dato

| Código (requiere deploy) | Dato (lo edita el super administrador) |
|---|---|
| Algoritmos `ponderado`, `luhn`, `compuesto`, `pa_ruc_dv` (y el alias `resto_entero`) | Algoritmo elegido y sus parámetros por tipo |
| Validadores de componentes `fecha`, `catalogo`, `distinto_de`, `lista_negra` | Posiciones, formatos y listas de valores |
| Primitivas de normalización (quitar, mayúsculas, rellenar, partes) | Qué primitivas aplica cada tipo |
| Armado de la máscara (izquierda o derecha) | La máscara y su alineación |
| Motor de autoprueba y de simulación | Ejemplos válidos e inválidos; excepciones; relaciones `contiene_a`; vigencias; fuentes |

Un país nuevo con documentos «de manual» (solo dígitos, un DV ponderado) se agrega **sin deploy**. Un país con un algoritmo raro (como Panamá) necesita código una sola vez.

---

## 7. Casos difíciles detectados

1. **Alfanuméricos y letras con valor numérico:** CURP y RFC (Ñ, `&`, espacio en el alfabeto del RFC), RIF (la letra entra en la suma), DV `K` (Chile, Guatemala), carácter de control del DNI de Perú (dígito **o** letra), NIE y NIF de España, complemento de Bolivia, letras de Panamá (`E`, `N`, `PE`, `PI`, `AV`, `NT`, que el DV traduce a números).
2. **Separadores con significado y ceros omitidos:** en Panamá los guiones separan partes de largo variable; en Costa Rica se omiten los ceros de cada parte. Normalizar «quitando guiones» rompe los dos casos. Hace falta la primitiva `partes`.
3. **Números que cambian o se reemplazan:**
   - NIT de persona en El Salvador → DUI (2022), salvo menores, extranjeros y personas jurídicas.
   - NIT de Guatemala → los 9 primeros dígitos del CUI (2025).
   - CUIT/CUIL de Argentina: prefijo 23 cuando el DV daría 10, y asignación no binaria de prefijos.
   - RUC jurídico de Panamá (2014).
   - En Colombia, los menores pasan de tarjeta de identidad a cédula: con el mismo NUIP desde 2003, pero con números distintos antes.
   - Nueva cédula de República Dominicana (2026) y nuevo formato de Nicaragua (2026): si cambian el número, NO VERIFICADO.
   - Proyecto de número permanente en Cuba.
   - **Consecuencia:** el documento de la persona puede tener historial; `vigente_desde/hasta` en el tipo y baja lógica del documento viejo, sin pisarlo.
4. **Varios documentos válidos por persona** (al menos 14 países): identidad + fiscal + a veces otro (CURP + RFC + credencial INE en México). Modelo: N documentos por persona, uno principal y relaciones `contiene_a` para proponer y cruzar.
5. **Números no únicos:** Bolivia (unos 400.000 duplicados → complemento); Paraguay (rangos bloqueados por falsificación). La clave única es (tipo, número, complemento), y un número sin complemento que choca no puede darse por la misma persona.
6. **Números válidos que no cumplen su propio DV:** unas 578 cédulas de República Dominicana y RNC históricos (lista de excepciones); alrededor del 1,5 % de los RFC (`nivel_dv = advertencia`). Validar «a rajatabla» rechazaría a personas reales.
7. **Documentos sin DV** (DNI de Argentina, CI de Paraguay, CI de Bolivia, CC de Colombia, cédula de Venezuela, DNI de Honduras, cédulas de Costa Rica y Panamá): solo se controla el formato, así que los errores de tipeo pasan. Mitigación: cruce con el identificador fiscal derivado (el DNI dentro del CUIL), confirmación visual con la máscara y doble ingreso en altas públicas.
8. **Menores:** en algunos países el documento existe desde el nacimiento (DNI de Argentina, CURP, CUI, DNI de Perú, NUIP de Colombia); en otros hay edad mínima (DUI y cédula de Ecuador, 18). Un menor puede no tener documento propio: hace falta el estado «sin documento / en trámite» y el vínculo con el adulto responsable, sin inventar números (regla de ZARIS: nunca escribir datos falsos en la BUC).
9. **Extranjeros:** cada país tiene su documento de residente (DIMEX, CE, PPT, NIE, cédula E, «E-» de Panamá, NT) y además existe el pasaporte del país de origen. Modelo: tipo genérico `PASAPORTE` (`pais` NULL en el tipo) + país emisor en el documento + regex laxa (`^[A-Z0-9]{5,20}$`, **NO VERIFICADA** contra estándares de cada país).
10. **El algoritmo oficial no está publicado** en la mayoría de los casos; la fuente es técnica. `estado_verificacion` lo deja a la vista y `nivel_dv` permite degradar a advertencia.
11. **DV de 2 dígitos con conflicto de ejemplos** (Panamá).
12. **Ley aplicable:** el tratamiento lo regula la ley del **país del municipio**, no la del país emisor del documento. Un municipio argentino que guarda una cédula paraguaya aplica la Ley 25.326.
13. **ZARIS hoy:** `_validar_modulo11` acepta resto 1 → DV 9 sin mirar el prefijo, igual que python-stdnum. El catálogo de Argentina puede sembrarse idéntico (compatibilidad) o en modo estricto. **Es una decisión de producto, no de este informe.** Además, el login interpreta «solo dígitos, 7 u 8» como DNI: esa regla tiene que pasar a leer el `patron` del documento principal del país del municipio.

---

## 8. Fuentes

Bibliotecas técnicas usadas en todo el informe:
- **[F70]** python-stdnum 2.2 (Arthur de Jong). Se descargó y se leyó el código fuente; los ejemplos se ejecutaron. Paquete: https://pypi.org/project/python-stdnum/2.2/ · documentación por módulo: https://arthurdejong.org/python-stdnum/doc/ (ej. https://arthurdejong.org/python-stdnum/doc/stdnum.cu.ni ) · código: https://github.com/arthurdejong/python-stdnum/tree/master/stdnum. Módulos citados: `ar.dni`, `ar.cuit`, `uy.rut`, `cl.rut`, `py.ruc`, `pe.cui`, `pe.ruc`, `ec.ci`, `ec.ruc`, `co.nit`, `ve.rif`, `mx.curp`, `mx.rfc`, `gt.nit`, `sv.nit`, `cr.cpf`, `cr.cpj`, `cr.cr`, `cu.ni`, `do.cedula`, `do.rnc`, `es.dni`, `es.nie`, `es.cif`, `luhn`.
- **[F72]** stdnum para JS 1.12.6 (koblas). Se descargó con `npm pack` y se ejecutó la compilación CJS. https://www.npmjs.com/package/stdnum · https://github.com/koblas/stdnum-js. Módulos: `uy/cedula`, `uy/nie`, `py/cedula`, `bo/ci`, `pe/ce`, `gt/cui`.
- **[F73]** ci_js (validador de CI de Uruguay): https://raw.githubusercontent.com/picandocodigo/ci_js/master/ci.js
- **[F71]** Wikipedia, «Clave Única de Identificación Tributaria»: https://es.wikipedia.org/wiki/Clave_Única_de_Identificación_Tributaria

Fichas oficiales de TIN entregadas por cada administración tributaria a la OCDE (portal del CRS), patrón `https://www.oecd.org/tax/automatic-exchange/crs-implementation-and-assistance/tax-identification-numbers/<País>-TIN.pdf`:
- [F1] Argentina-TIN.pdf · [F4] Uruguay-TIN.pdf (actualizada el 27/06/2025) · [F7] Chile-TIN.pdf · [F18] Peru-TIN.pdf · [F20] Ecuador-TIN.pdf · [F23] Colombia-TIN.pdf · [F31] Mexico-TIN.pdf · [F48] Costa-Rica-TIN.pdf · [F50] Panama-TIN.pdf · [F58] Spain-TIN.pdf

Por país:
- [F2] AR, Ley 17.671 citada en la Disposición RENAPER 82/2020: https://www.colegio-escribanos.org.ar/noticias/2020_01_29-RENAPER-Disposicion-82-20.pdf · https://www.boletinoficial.gob.ar/detalleAviso/primera/224939/20200129
- [F3] AR, Ley 25.326: https://www.argentina.gob.ar/normativa/nacional/64790/texto · https://www2.hcdn.gob.ar/export/hcdn/secparl/dgral_info_parlamentaria/dip/archivos/Ley_25326.pdf
- [F5] UY, Decreto 501/978 (IMPO): https://impo.com.uy/bases/decretos-originales/501-1978
- [F6] UY, Ley 18.331 y Decreto 414/009: https://impo.com.uy/bases/leyes-originales/18331-2008 · https://impo.com.uy/bases/decretos/414-2009
- Ejemplos de la CI de Uruguay (secundarias): https://hacecuentas.com/uy/validar-cedula · https://documat.unirioja.es/descarga/articulo/6636701.pdf
- [F8] CL, Ley 21.719: https://www.diarioconstitucional.cl/2026/06/12/la-ley-21-719-entra-en-vigor-el-1-de-diciembre-y-expone-vacios-en-regulacion-de-pequenas-empresas/ · https://academiajudicial.cl/recursos/actualizaciones-normativas/ley-21-719-que-regula-la-proteccion-y-el-tratamiento-de-los-datos-personales-y-crea-la-agencia-de-proteccion-de-datos-personales/ · Ley 19.628: https://www.suseso.gob.cl/612/w3-propertyvalue-74976.html
- [F9] PY, rangos bloqueados: https://www.ultimahora.com/usaron-numeros-bloqueados-cedulas-n2873746
- [F10] PY, DNIT (Ley 7143/2023): https://ferrere.com/es/novedades/paraguay-aprueba-la-fusion-de-la-autoridad-tributaria-y-aduanera-creando-la-direccion-nacional-de-ingresos-tributarios/
- [F11] PY, ejemplo y regla del DV del RUC (secundaria): https://yo-facturo.com/herramientas/validador-ruc-paraguay/
- [F12] PY, Ley 7593/2025: https://www.bacn.gov.py/leyes-paraguayas/12924/ley-n-75932025--de-proteccin-de-datos-personales-en-la-repblica-del-paraguay · https://iapp.org/news/a/paraguay-da-un-paso-hacia-un-marco-moderno-de-protecci-n-de-la-privacidad
- [F13] BO, complemento y duplicados: https://boliviaimpuestos.com/complemento-del-carnet-de-identidad/ · https://eju.tv/?p=158009 · DS 4924/2023 (SEGIP, Ley 145): https://www.lexivox.org/norms/BO-DS-N4924.html
- [F14] BO, DS 4861/2023: https://www.lexivox.org/norms/BO-DS-N4861.html
- [F15] BO, falta de ley y anteproyecto: https://agetic.gob.bo/wp-content/uploads/2024/08/DATOS-PERSONALES-PRESENTACION-ANTEPROYECTO-DE-LEY-2024-firmado.pdf · https://editorial.upds.edu.bo/index.php/fupds/es/catalog/download/11/6/78?inline=1
- [F16] PE, Ley 26497 y Ley 32237: https://www.congreso.gob.pe/Docs/GrupoTrabajo2016/Constitucion_ReformaElectoral/files/baselegal/26497-reniec.pdf · https://busquedas.elperuano.pe/dispositivo/NL/2371125-1
- [F17] PE, carácter de control (prensa): https://infomercado.pe/reniec-dni-para-que-sirve-el-digito-verificador
- [F19] PE, DS 016-2024-JUS: https://www.gob.pe/institucion/anpd/normas-legales/6554453-16-2024-jus
- [F21] EC, LOPDP: https://faolex.fao.org/docs/pdf/ecu213345.pdf · https://derechoecuador.com/ley-organica-de-proteccion-de-datos-personales/
- [F22] CO, Resolución Registraduría 3571 de 2003: https://cancilleria.gov.co/sites/default/files/Normograma/docs/resolucion_registraduria_3571_2003.htm
- [F24] CO, ejemplo de DV del NIT: https://siemprealdia.co/colombia/impuestos/digito-de-verificacion-del-nit/
- [F25] CO, Ley 1581 de 2012: https://www.funcionpublica.gov.co/eva/gestornormativo/norma.php?i=49981
- [F26] VE, Ley Orgánica de Identificación 2006: https://venezuela.justia.com/federales/leyes-organicas/ley-organica-de-identificacion/gdoc/
- [F27] VE, estructura del RIF (prensa): https://www.bloomberglinea.com/latinoamerica/venezuela/consulte-y-descargue-aqui-la-planilla-para-sacar-el-rif-por-primera-vez/
- [F28] VE, Providencia SNAT/2026/00080: https://www.pwc.com/ve/es/assets/documentos/stl/NAC-SENIAT-Resoluciones-20260814-2026.pdf · https://accesoalajusticia.org/reforma-de-la-providencia-administrativa-que-regula-el-rif/
- [F29] VE, sin ley especial: https://iapp.org/news/a/venezuela-data-breach-highlights-scattered-privacy-regulation · https://zenodo.org/records/16368307
- [F30] MX, Instructivo normativo CURP (2018): https://sidof.segob.gob.mx/notas/docFuente/5526717
- [F32] MX, LGPDPPSO y LFPDPPP 2025: https://www.diputados.gob.mx/LeyesBiblio/pdf/LGPDPPSO.pdf · https://www.diputados.gob.mx/LeyesBiblio/pdf/LFPDPPP.pdf
- [F33] GT, Decreto 39-2010 (reforma del art. 4 del Decreto 90-2005): https://www.renap.gob.gt/sites/default/files/informacion-publica/1_decreto_39-2010_reformas_a_la_ley_del_registro_nacional.pdf
- [F34] GT, estructura del CUI (sin algoritmo): https://learn.sayari.com/interpreting-guatemalan-national-id-numbers/
- [F35] GT, unificación CUI-NIT (AGN): https://agn.gt/sat-aclara-que-unificacion-del-cui-y-el-nit-no-devela-informacion-bancaria/ · https://agn.gt/?p=430375 (las URLs de agn.gt devolvieron 403 al abrirlas; el contenido sale del índice del buscador) · reglas FEL de la SAT citadas por stdnum (403): https://portal.sat.gob.gt/portal/descarga/6524/factura-electronica-fel/25542/fel-reglas-y-validaciones.pdf
- [F36] GT, datos personales: https://www.dataguidance.com/jurisdiction/guatemala · https://iapp.org/news/b/data-protection-law-initiative-advances-in-guatemala · https://www.prensalibre.com/wp-content/uploads/2019/12/EDP_Guatemala.pdf
- [F37] HN, estructura del número de identidad: https://camjol.info/index.php/LRD/article/download/1253/1080/4448
- [F38] HN, RTN (prensa): https://www.elheraldo.hn/tramites/como-tramitar-registro-tributario-nacional-rtn-CM28063537 · https://www.laprensa.hn/portada/verificacion-falso-rtn-costo-1500-lempiras-sar-DI31283752
- [F39] HN, anteproyecto de ley de datos: https://www.elheraldo.hn/honduras/socializan-anteproyecto-ley-proteccion-datos-personales-DC21765161
- [F40] SV, Ley Especial del DUI: https://www.jurisprudencia.ues.edu.sv/oajc/leyes/LegislacionCivil/Ley%20Especial%20Reguladora%20de%20la%20Emision%20del%20Documento%20Unico%20de%20Identidad.pdf
- [F41] SV, algoritmo del DUI (foro comunitario): https://www.svcommunity.org/forum/programacioacuten/como-calcular-digito-verificador-del-dui-y-nit/msg951882/
- [F42] SV, módulo de Odoo: https://apps.odoo.com/apps/modules/18.0/l10n_latam_sv
- [F43] SV, homologación NIT-DUI (Ministerio de Hacienda): https://www.mh.gob.sv/homologacion-de-nit-y-dui-simplifica-tramites/ · ley vigente: https://transparencia.mh.gob.sv/downloads/pdf/DC5823_Ley%20del%20NIT.pdf
- [F44] SV, aplicación desde el 1-07-2022: https://www.elsalvador.com/noticias/negocios/pasos-para-homologar-nit-con-dui-ministerio-hacienda/964632/2022/
- [F45] SV, Ley de Protección de Datos Personales (D.L. 144/2024): https://transparencia.mh.gob.sv/downloads/pdf/700-UAIP-LY-2024-14993.pdf · https://www.hrw.org/es/news/2024/12/12/el-salvador-nuevas-leyes-amenazan-la-libertad-de-expresion-y-la-privacidad
- [F46] NI, Ley 152 y nuevo formato: https://nicaragua.justia.com/nacionales/leyes/ley-de-identificacion-ciudadana-mar-5-1993/gdoc · https://www.laprensani.com/2026/02/24/nacionales/3635949-dictadura-pone-imagen-de-sandino-en-el-reverso-de-la-nueva-cedula-de-identidad
- [F47] NI, Ley 787 y su reglamento: https://nicaragua.justia.com/nacionales/leyes/ley-de-proteccion-de-datos-personales-mar-29-2012/gdoc · https://nicaragua.justia.com/nacionales/decretos-ejecutivos/reglamento-de-la-ley-no-787-ley-de-proteccion-de-datos-personales-oct-19-2012/gdoc
- [F49] CR, Ley 8968: https://www.tse.go.cr/pdf/normativa/reglamentoleyproteccionpersona.pdf · https://www.micitt.go.cr/sites/default/files/marco_juridico_legal/08.%20Ley%20n.%C2%B0%208968%20Ley%20de%20Protecci%C3%B3n%20de%20la%20Persona%20frente%20al%20tratamiento%20de%20sus%20datos%20personales..pdf
- [F51] PA, documento DGI «Algoritmo para el cálculo del DV» v201805 (copia en GitHub): https://github.com/juancorradine/Panama-RUC-DV-Calculator/blob/master/dgi/Calculo_Digito_Verificador_RUC.pdf · implementación contrastada: https://pypi.org/project/panama-ruc-dv-calculator/ (1.0.4)
- [F52] PA, Ley 81/2019 y DE 285/2021: https://lexlatin.com/entrevistas/reglamento-la-ley-proteccion-datos-panama · https://vlex.com.pa/vid/decreto-ejecutivo-285-2021-1049776104
- [F53] CU, proyecto de ley de identidad: https://www.cubanet.org/regimen-cubano-propone-ley-para-registrar-voz-iris-y-otros-datos-biometricos-de-la-poblacion/
- [F54] CU, Ley 149/2022: https://www.mincom.gob.cu/es/print/5823 · https://www.dataguidance.com/jurisdiction/cuba
- [F55] DO, cédula: https://en.wikipedia.org/wiki/National_Identity_Card_(Dominican_Republic) · https://elnuevodiario.com.do/la-cedula-de-identidad-y-electoral-un-pequeno-plastico-convertido-en-testimonio-de-identidad-y-ciudadania/
- [F56] DO, RNC (secundaria): https://siemprealdia.co/republica-dominicana/impuestos/que-es-rnc/
- [F57] DO, Ley 172-13: https://pwc.com/ia/es/servicios/Regulacion-Legal/RD-Ley-172-13%20.pdf
- [F59] ES, LOPDGDD (BOE-A-2018-16673): https://www.boe.es/buscar/act.php?id=BOE-A-2018-16673

---

## 9. Puntos NO VERIFICADOS (consolidado)

1. AR: que la ANSES sea el emisor del CUIL (la ficha OCDE solo dice que se otorga con el DNI).
2. AR: el algoritmo oficial del DV del CUIT (la ficha OCDE dice «asignado al azar»; el algoritmo usado es técnico) y la regla de cambio de prefijo a 23 o 33 (solo Wikipedia).
3. AR: si los documentos de menos de 7 dígitos (LE/LC) siguen vigentes como identificación.
4. UY: los pesos `2,9,8,7,6,3,4` de la CI (el decreto oficial solo dice «módulo diez»).
5. UY: el algoritmo del DV del NIE.
6. PY: el formato oficial de la CI (5 a 7 dígitos) y el documento técnico de la DNIT con el algoritmo del RUC.
7. BO: la longitud del número de CI, el formato del complemento, si la extensión del departamento forma parte del número y la estructura del NIT.
8. PE: el formato del carné de extranjería; que el algoritmo del carácter de control del DNI sea el de RENIEC.
9. CO: los formatos de CE, PEP y PPT; la longitud de las cédulas anteriores a 2003.
10. VE: la reforma de 2014 de la Ley Orgánica de Identificación; la longitud de la cédula; las letras del RIF distintas de V, E, J, P, G; el art. 28 de la Constitución como base del hábeas data.
11. MX: el algoritmo oficial del DV de la CURP y del RFC (son técnicos); las leyes estatales de datos personales; el formato de la CURP de extranjeros.
12. GT: el algoritmo oficial del DV del CUI y qué pasa cuando el resto es 10; el documento de la SAT con el algoritmo del NIT (403 al abrirlo); si el NIT tiene 9 o 13 dígitos tras la unificación (AGN dice 9; una fuente comercial dice 13).
13. HN: el desglose departamento, municipio, año y correlativo del DNI; el cálculo del dígito 14 del RTN; la estructura del RTN de personas jurídicas; la existencia y el número de una ley de datos (el «Decreto 25-2013»); el número de decreto de la Ley de Transparencia (170-2006).
14. SV: el algoritmo del DV del DUI (solo fuente comunitaria); no hay un DUI válido de ejemplo.
15. NI: la estructura de la cédula y el algoritmo de su letra final; la estructura del RUC y el prefijo «J»; el estado de la Ley 1241 de 2025.
16. PA: el algoritmo del DV de 2 dígitos (la implementación pública no reproduce 4 de los 7 ejemplos, incluidos 4 de la OCDE); el patrón completo de normalización de todas las variantes de cédula; que el documento DGI publicado en GitHub sea la versión vigente.
17. CU: el emisor (MININT); si el dígito 11 es un DV y su algoritmo; el formato del NIT de la ONAT; el estado del proyecto de número de identidad permanente.
18. DO: si la cédula nueva (2026) cambia el número; el algoritmo oficial (Luhn es técnico); que las personas físicas usen la cédula como RNC (solo fuentes secundarias).
19. CL: si la Ley 21.719 se posterga al 1-12-2027 (Boletín 18.623-07 en trámite al 23-10-2026).
20. General: la regex laxa propuesta para pasaportes; el patrón tentativo de Panamá en §4.4.
