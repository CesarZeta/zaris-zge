# Memoria del proyecto ZARIS (versión curada para colaboradores)

> Esta carpeta es una **copia curada** de la memoria de trabajo del proyecto, pensada
> para que cualquier colaborador (con o sin Claude Code) reaproveche el conocimiento
> acumulado: quirks del stack, patrones validados, decisiones de diseño y aprendizajes.
>
> **Qué NO está acá (a propósito):** se excluyeron las memorias con credenciales,
> DNIs, casillas reales o mapas internos de seguridad — el repo es **público**
> (CLAUDE.md §40). Los valores sensibles residuales fueron enmascarados
> (`<PASS-DEMO>`, `<USUARIO-DEMO>@…`, etc.). Para credenciales de prueba o el estado
> de sesión, pedíselos al admin del proyecto por canal privado.
>
> **Cómo usarlas con Claude Code:** son archivos Markdown estándar. Si querés que tu
> agente las use como memoria persistente, copialas a tu propio
> `~/.claude/projects/<...>/memory/` (no se cargan automáticamente desde `docs/`).
> Si solo querés leerlas, abrí los `.md` directamente.

---

## Índice

- [Verificar siempre antes de opinar (REGLA DE POR VIDA)](feedback_verificar_siempre_antes_de_opinar.md) — contrastar con DB/código/runtime/navegador antes de afirmar.
- [Manuales sin fechas ni nombres](feedback_manuales_sin_fechas_ni_nombres.md) — docs/manual_*.html: nunca fecha ni nombre de usuario.
- [Usuario vs Ciudadano](project_usuario_vs_ciudadano_modelo.md) — vecino scope publico, autoservicio acotado a lo suyo.
- [Portal del Ciudadano (PWA zaris-vecinos)](project_portal_ciudadano_pwa.md) — etapas A-E cerradas; sesión zaris_vecino_session.
- [Roy — colaborador App Vecinos](project_roy_colaborador_app_vecinos.md) — dev (no QA); PWA ciudadano + funcionario; acceso completo a prod.
- [Autogestión no afloja datos obligatorios](feedback_autogestion_no_afloja_obligatorios.md) — el form del vecino nunca pide menos que el alta interna.
- [SW de la PWA: build viejo + push](feedback_pwa_service_worker_sirve_build_viejo.md) — SW sirve build viejo; /sw.js MIME dev/preview.
- [Loop de envío: probar ambas fallas](feedback_loop_envio_probar_ambas_fallas.md) — catch POR item; dato mal formado Y destino muerto.
- [useSyncExternalStore: cachear getSnapshot](feedback_usesyncexternalstore_getsnapshot_cache.md) — JSON.parse da ref nueva → loop; cachear vs string crudo.
- [Geocoding vecino: scope publico](reference_geocoding_vecino_endpoint_scope_publico.md) — /publico/reclamos/geo/buscar.
- [Verificar superficies externas](feedback_verificar_superficies_externas_y_recuerdo_usuario.md) — "No lo veo" ≠ "no existe".
- [Folletos comerciales locales](reference_folletos_comerciales_locales.md) — en folletos/ (gitignored, NO docs/).
- [SKILL.md: render expande $N y cachea](reference_skill_render_expande_dolar_y_cachea.md) — no $1 literal; validar fix en sesión nueva.
- [python3 no está en el Bash tool](reference_no_python3_en_bash_tool.md) — falla silencioso; editar con Edit/Write.
- [Regla vs receta para skills](feedback_regla_vs_receta_para_skills.md) — CLAUDE.md gobierna sin invocar; skill = tarea deliberada.
- [No batch grande: un fallo cancela todo](feedback_no_batch_grande_un_fallo_cancela_todo.md) — 1 Edit/msg; Read antes de cada Edit.
- [Módulo React nuevo necesita fila en `modulos`](feedback_modulo_react_necesita_fila_en_modulos.md) — sin fila del data-modulo, el ítem se oculta.
- [El backend puede mentir (3 caras)](feedback_el_backend_puede_mentir.md) — shape JSON ≠ tipo TS · openapi() crashea · SELECT omite columna.
- [Columna nueva: auditar todos los SELECT](feedback_columna_nueva_auditar_todos_los_select.md) — el que la omite da undefined; tocar helper + GET handler.
- [Filtro `= :param` con NULL vacía el listado](feedback_filtro_igual_null_vacia_listado.md) — "bandeja vacía" → filtro SQL con param NULL.
- [Trámites: pico de errores por feature grande](project_tramites_pico_errores_feature_grande.md) — partir + verificar.
- [apply_migration parcial aborta TODO](feedback_apply_migration_parcial_aborta_todo.md) — atómico; un statement que falla revierte el script.
- [CHECK NOT VALID se evalúa al UPDATE](feedback_check_not_valid_se_evalua_al_update.md) — UPDATE de fila vieja la obliga; backfillar en el UPDATE.
- [encuesta_envio polimórfico (LEFT JOIN)](encuesta_envio_polimorfico_left_join.md) — mig 72: id_reclamo XOR id_turno; branch por origen.
- [Turnos: disponibilidad por recurso + novedades](project_turnos_disponibilidad_novedades_feriados.md) — mig 69/70, turno polimórfico, switch global.
- [Trámites: aprobaciones por etapa](project_tramites_aprobaciones_por_etapa.md) — visados/subsanación, mig 73.
- [Trámites: destinatario=agente + Mi bandeja](project_tramites_destinatario_agente_y_mi_bandeja.md) — mig 66, GET /mi-bandeja + /destinatarios.
- [Trámites: storage en Supabase](project_tramites_storage_efimero_deuda.md) — backend sube binario tras SHA256.
- [Trámites: retención de documentos](project_tramites_retencion_documentos.md) — flag por tipo, auto-archivado 180d, purga dry-run, cron.
- [Lineamientos de visualizaciones BI](reference_bi_lineamientos_visualizaciones.md) — totales+pastilla oscura, recharts 2, agregación en SQL.
- [Normalizar JSONB de seeds viejos](feedback_normalizar_jsonb_de_seeds_viejos.md) — el shape en DB puede no ser el del editor; normalizar antes de .map.
- [Validación reactiva vs cambios programáticos](feedback_validacion_reactiva_cambios_programaticos.md) — botón queda gris al poblar form por código.
- [Triggers documentados pueden no existir](feedback_verificar_trigger_existe_no_confiar_doc.md) — CLAUDE.md afirmaba trg_nro_ot pero no existía.
- [Guard de subárea: cubrir TODAS las vías](feedback_guard_subarea_cubre_todas_las_vias.md) — un bloqueo en una sola ruta deja abiertas las demás.
- [Config sistema: pantalla tipada](reference_config_sistema_pantalla_tipada.md) — tab Sistema edita configuracion_general tipado.
- [Railway bloquea egress SMTP — Resend](reference_railway_bloquea_egress_smtp.md) — Resend API HTTP/443; enviar_mail async.
- [pydantic extra_forbidden al borrar settings](feedback_pydantic_extra_forbidden_al_borrar_settings.md) — borrar vars tumba el backend si quedan env vars viejas.
- [git checkout destruye ediciones de sesión](feedback_git_checkout_destruye_ediciones_sesion.md) — revierte el working tree completo, no "pausa".
- [Aprendizajes del proyecto](feedback_aprendizajes_proyecto.md) — compendio histórico; releer al tocar DB/migraciones.
- [MANDATORIO: verificar forms/UI navegando](feedback_verificar_forms_navegando_mandatorio.md) — la hago YO (browser MCP); tabs reales, no URL directa.
- [Form inline en admin_tablas fuera de #main](reference_admin_tablas_form_inline_fuera_de_main.md) — #main se reescribe; el form inline va hermano fuera.
- [Vincular siempre por ID](feedback_vincular_por_id.md) — FK por id, no matching de strings.
- [Push directo a main](feedback_push_directo_a_main.md) — con todo en verde avanzar sin confirmar; si hay error/intervención, PARAR.
- [Shell principal ZARIS](project_shell_entry.md) — el shell real es `index.html` en la raíz.
- [tipo_reclamo área — fuente única](project_tipo_reclamo_area_inconsistencia.md) — área SIEMPRE vía JOIN con subarea (mig 27).
- [Dar links concretos al pedir test visual](feedback_dar_links_para_testear.md) — pasar URL local/prod; nunca instrucciones de navegación.
- [Shell PS vs Bash](feedback_shell_ps_vs_bash.md) — `$env:VAR=` o `Set-Location` van por PowerShell, NO Bash.
- [Web-app redirect-a-login](feedback_diagnosticar_redirect_login.md) — sospechar `getToken()`/handler 401 en lib/api.ts antes que router/CSS.
- [Verbos HTTP agenda_v2](reference_agenda_v2_verbos_http.md) — PATCH cancelar/asistio/resolver; `grep @router` antes de scriptear.
- [Shape zaris_session](project_zustand_persist_session_shape.md) — web-app `{state:{accessToken,user}}`, vanilla `{access_token,user}`.
- [Grillas con useDroppable y clicks](feedback_grilla_droppable_clicks.md) — no onClick en el wrapper droppable ni draggables full-bleed.
- [Nomenclatura shell vanilla / React / módulos](feedback_nomenclatura_shell.md) — no decir "web-app" como producto.
- [Verificar runtime antes de agente externo](feedback_verificar_runtime_antes_de_agente.md) — curl /openapi.json antes de gastar el agente.
- [Patrón deploy módulo React](project_patron_deploy_modulo_react.md) — publicar un módulo React embebido en el shell vanilla.
- [Misma magnitud en 2 endpoints diverge](feedback_misma_magnitud_dos_endpoints_diverge.md) — unificar en 1 fn (singular+batch); comparar superficies.
- [DnD sintético no funciona](feedback_dnd_sintetico_no_funciona.md) — @dnd-kit requiere isTrusted=true; dispatchEvent NUNCA activa el sensor.
- [Proxy local /zaris-zge/](project_proxy_local_zaris_zge.md) — probar shell vanilla + bundle React embebido sin GH Pages.
- [Browser-mcp + React: setup via API](feedback_browser_mcp_react_setup.md) — alta por form: POST por API + reload.
- [Verificar drift COMPLETO en prod](feedback_verificar_drift_completo_prod.md) — 4 dims: existencia + CHECKs + defaults + seeds.
- [Verificar que los datos EXISTEN antes de buscar](feedback_verificar_datos_existen_antes_de_flujo_busqueda.md) — COUNT FILTER antes de codear.
- [FKs entrantes son alcance al dropear tabla](feedback_fks_entrantes_son_alcance.md) — listar FKs entrantes; cada una viva = decisión al usuario.
- [Cotizar refactor UI exige leer el CSS](feedback_cotizar_refactor_ui.md) — abrir el archivo antes de prometer horas.
- [Smoke listar users primero](feedback_smoke_listar_users_primero.md) — mapear email↔id↔nivel; loguear inputs reales.
- [Grep DS antes de crear componentes](feedback_grep_DS_antes_de_crear.md) — antes de naming nuevo, grep el DS.
- [Shell React no carga components.css](feedback_shell_react_no_carga_components_css.md) — solo tokens, NO los componentes `*-zaris`.
- [Calibrar alcance antes de migrar](feedback_calibrar_alcance_migracion.md) — `wc -l` + grep endpoints ANTES de prometer.
- [cwd Bash + cd relativo no es confiable](feedback_cwd_bash_cd_relativo.md) — usar paths absolutos en Write/Edit.
- [BUC guarda CUIL/CUIT sin guiones](reference_buc_cuil_sin_guiones.md) — `_validar_modulo11` retorna `limpio`; UI normaliza al mostrar.
- [apiFetch vanilla ya antepone /buc](feedback_apifetch_ya_antepone_buc.md) — `ZUtils.apiFetch` usa API_BUC que ya termina en /api/v1/buc.
- [Verificar CHECK antes de codear selects](feedback_verificar_check_antes_de_select.md) — antes de tipear un union, grep el CHECK en prod.
- [Datos de prueba se CONSERVAN como demo](feedback_smoke_cleanup_prod.md) — ya NO se limpian smokes/QA en prod.
- [Browser-MCP React: lo que SÍ funciona](feedback_browser_mcp_que_si_funciona.md) — Leaflet map.on, DataTransfer en file inputs, button.click().
- [browser-MCP iframe cache](feedback_browser_mcp_iframe_cache.md) — el iframe cachea el bundle viejo; `frame.src += '&_t=NOW'`.
- [Reportes ambiguos del usuario](feedback_reportes_ambiguos_usuario.md) — "logo", "icono", "shell", "navegación" significan cosas distintas.
- [Verificar destino antes de migrar link sidebar](feedback_verificar_destino_link_sidebar.md) — que el destino llega al resto en iframe.
- [No sugerir Chrome DevTools / Playwright MCP](feedback_no_sugerir_mcp_navegador.md) — usar integrated-browser-mcp.
- [Redirect iframe respeta subpath](feedback_redirect_iframe_subpath.md) — `window.location.href='/foo'` del bundle rompe bajo /zaris-zge/.
- [Guard sesión en <head> antes del iframe](feedback_guard_sesion_en_head.md) — el script de sesión va en `<head>` de index.html.
- [Verificar env vars Railway tras push backend](feedback_verificar_env_vars_railway.md) — Railway tiene su set propio; testear prod.
- [Cache-bust ?v= en assets estáticos](feedback_cache_bust_assets_estaticos.md) — al editar menu.css/menu.js, bumpear el sufijo `?v=`.
- [asyncpg + text() — params tipados](feedback_asyncpg_extract_cast_date.md) — `CAST(:p AS tipo)`, `make_interval(days=>:p)`; body:dict → date/time.
- [Agenda B1+B2 cerradas, perf optimizada](project_agenda_espacios_disponibilidad.md) — en prod; /calendario 23s→2.2s.
- [Uvicorn restart tras registrar routers](feedback_uvicorn_restart_tras_registrar_routers.md) — sin --reload sirve código viejo; matar por puerto.
- [Proponer fases antes de codear](feedback_proponer_fases_antes_de_codear.md) — verificar realidad + AskUserQuestion + acordar fases.
- [Table<T> de web-app/ui tiene bound hostil](feedback_table_ui_bound_hostil.md) — `T extends Record<string,unknown>` rechaza interfaces.
- [Ampliar unión central exige grep de consumers](feedback_ampliar_union_grep_consumers.md) — decidir cuál acepta vs restringe.
- [Clave dict /agenda/semana es "tipo:id"](reference_agenda_semana_disponibilidad_key.md) — `disponibilidad_por_recurso` usa `"{tipo}:{id}"`.
- [Patrón batch helper + singular wrapper](feedback_patron_batch_helper_singular_wrapper.md) — loops N queries → fn_batch 1-2 queries + wrapper.
- [Latencia base Railway↔Supabase ~2-3s](reference_agenda_latencia_base_railway_supabase.md) — piso con JOINs; no prometer sub-segundo.
- [PS $Global no persiste entre tool-calls](feedback_ps_global_no_persiste.md) — login + uso del token en el MISMO bloque.
- [Polling con login DENTRO del loop](feedback_polling_login_dentro_del_loop.md) — 502 transitorio; login fuera arrastra iteraciones.
- [No `gh` CLI — usar REST](reference_no_gh_cli_usar_rest.md) — `Invoke-RestMethod` contra api.github.com/repos/.../actions/runs.
- [Leer DOM bruto antes de declarar bug visual](feedback_leer_dom_antes_de_declarar_bug.md) — si un selector devuelve menos elementos de los esperados.
- [useEffect con `data ?? []` loop](feedback_useeffect_data_null_loop.md) — `data ?? []` da ref nueva; setter con new Set/[...].
- [Cross-module imports en React](feedback_cross_module_imports_react.md) — OK importar de otro módulo si comparten el recurso backend.
- [PowerShell execution policy bloquea pnpm](feedback_powershell_execution_policy_pnpm.md) — `pnpm typecheck` desde tool PS falla con UnauthorizedAccess.
- [Seedear cuando la mesa está vacía](feedback_seedear_cuando_mesa_vacia.md) — setup <5min con cleanup obvio vence a "no validado".
- [Rebuild dist con working tree limpio](feedback_rebuild_dist_working_tree_limpio.md) — Vite compila TODO lo que está en disco, no lo staged.
- [Módulos Turnos y Entradas](project_modulos_turnos_entradas.md) — Turnos: tabla propia + ocupación espejo; Entradas: reusa eventos.
- [Quirks PS: Start-Process env + psql](feedback_ps_quirks_startprocess_psql.md) — env al hijo via `cmd /c "set VAR=..."`; psql sin PGPASSWORD cuelga.
- [Pendiente "verificar" = posible gap](feedback_pendiente_verificar_es_gap.md) — puede esconder código faltante; mapear el flujo.
- [browser_snapshot revienta tokens](feedback_browser_snapshot_revienta_tokens.md) — en páginas grandes; usar browser_eval puntual.
- [browser_eval 30s timeout en loop a Railway](feedback_browser_eval_timeout_loop_railway.md) — loop revienta CDP 30s; sembrar de a 1.
- [Validar FK antes del submit](feedback_validar_fk_antes_submit.md) — payload condicional por tipo: validar la FK con toast antes de enviar.
- [Select de agentes inusable en prod](feedback_select_agentes_es_inusable_en_prod.md) — 84 agentes; usar `RecursoPicker`.
- [Repaso visual del módulo caza bugs](feedback_repaso_visual_caza_bugs.md) — end-to-end en navegador saca bugs que typecheck no ve.
- [BUC ya tiene latitud/longitud](reference_buc_lat_lon_columnas_existentes.md) — ciudadanos y empresas YA tienen lat/lon en local y prod.
- [Columna DB no mapeada en ORM → setattr silencioso](reference_columna_db_no_mapeada_en_orm.md) — Ciudadano no mapea estado_validacion/ficha_completa; UPDATE SQL.
- [Filtrar POIs en /geo/buscar Nominatim](feedback_nominatim_filtrar_pois.md) — NO `layer=address`; limit=40 + reescribir display_name.
- [No backfill sobre datos sintéticos](feedback_no_backfill_sobre_datos_sinteticos.md) — leer 15 filas random antes: ¿son plausibles?
- [Dominio personalizado zge.zaris.com.ar](project_dominio_personalizado.md) — Cloudflare CNAME + GH Pages custom domain + vite base + CORS.
- [Leer patrón antes de implementar manifest React](feedback_leer_patron_existente_antes_de_implementar.md) — antes del index.tsx, leer types.ts + reclamos/.
- [Vite tree-shaking mata namespace icon lookup](feedback_vite_treeshaking_icons.md) — `import * as Foo` falla en prod para acceso dinámico.
- [EntitySelect recibe path no URL completa](feedback_entityselect_path_no_url.md) — `endpoint` debe ser `/api/v1/...`, NO `${BASE}/...`.
- [admin_tablas checklist tabla nueva](feedback_admin_tablas_checklist_tabla_nueva.md) — TABLE_CONFIG + sidebar + SCHEMAS + ICONS_MAP.
- [Columna NOT NULL sin DEFAULT en admin_tablas](feedback_columna_not_null_sin_default.md) — no-required + NOT NULL sin DEFAULT = INSERT 500.
- [react-pdf pin pdfjs-dist version](feedback_react_pdf_pin_pdfjs_version.md) — react-pdf@10.4.1 exige pdfjs-dist@5.4.296 exacto.
- [fetch cache binarios autenticados](feedback_fetch_cache_binarios_autenticados.md) — `fetch()` cachéa con Last-Modified; usar cache:'no-store'.
- [Service post-commit debe commitear](feedback_service_commit_propio.md) — service llamado DESPUÉS del commit hace `await db.commit()` propio.
- [tramite no tiene id_tipo_tramite directo](reference_tramite_no_tiene_id_tipo_tramite_directo.md) — FK via id_tipo_tramite_version → version → tipo.
- [Notificaciones in-app + email](project_notificaciones_in_app_email.md) — mig 51, 6 eventos, `enviada_mail=TRUE` persiste tras send.
- [TopBar React invisible en prod](feedback_features_topbar_react_invisibles_en_prod.md) — web-app/src/shell/TopBar/ solo en localhost:5173.
- [Browser MCP no persiste screenshots](feedback_screenshots_no_persisten_browser_mcp.md) — `filename:` de browser_screenshot NO guarda el PNG.
- [HTMLs autocontenidos: pestaña nueva](feedback_acortar_alcance_html_autocontenido.md) — base64 pesa; servir desde /docs/ + target=_blank.
- [Background tasks abren sesión SQL nueva](feedback_background_tasks_sesion_nueva.md) — la sesión del request ya está cerrada; usar `AsyncSessionLocal()`.
- [Filtros legacy `r.id_area` post-mig 27](feedback_filtros_legacy_post_mig27.md) — también en WHERE; `r.id_area=NULL` invisibles.
- [Verificar pendientes antes de atacarlos](feedback_verificar_pendientes_antes_de_atacar.md) — pueden estar resueltos; grep, git log, execute_sql.
- [Diff CLAUDE.md acumulado](feedback_diff_claude_md_acumulado.md) — leer el diff antes de stagear; doc atrasada: stash + commit dual.
- [`tsc -b --noEmit` vs `tsc --noEmit`](feedback_tsc_b_vs_noEmit.md) — el hook usa `-b`; verificar con el mismo comando.
- [Leer firmas de api.ts antes de consumir](feedback_verificar_firmas_api_antes_de_consumir.md) — antes de un componente que llame a lib/api.ts.
- [QA smoke: 3 casos de seguridad](feedback_qa_modulo_smoke_priorizar_seguridad.md) — endpoint sin JWT, XSS persistente, login real con user nuevo.
- [Triagear informe QA externo](feedback_triagear_informe_qa_externo.md) — clasificar bug/config/falso-positivo contra prod ANTES de codear.
- [Guard de nivel: backend, no solo UI](feedback_guard_nivel_endpoint_no_solo_ui.md) — restringir por rol solo en UI es evadible vía curl con JWT.
- [Body PS con acentos da 400](feedback_ps_body_utf8_acentos.md) — usar [Encoding]::UTF8.GetBytes(...) + charset=utf-8.
- [PS $var: se parsea como drive](feedback_ps_var_dos_puntos_es_drive.md) — "$id:" da ParserError; usar "${id}:". `??` no existe en PS5.1.
- [Smokes PS: @() antes de .Count](feedback_ps_smoke_array_count_y_datos_unicos.md) — 1 match da Count NULL; datos random por corrida.
- [CSS display pisa atributo hidden](reference_css_display_pisa_hidden.md) — `.x{display:flex}` + `<x hidden>` se ve igual. Fix: `.x[hidden]{display:none}`.
- [Síntoma del usuario no es el diagnóstico](feedback_sintoma_usuario_no_es_diagnostico.md) — verificar getComputedStyle ANTES de codear el fix.
- [Verificar fix de seguridad en prod durante deploy](feedback_verificar_fix_seguridad_en_prod_durante_deploy.md) — el 1er intento pega al código viejo y EJECUTA el bug.
- [Guard a nivel router vs por-handler](feedback_guard_a_nivel_router_vs_por_handler.md) — proteger router entero con APIRouter(dependencies=[...]).
- [No `git add <dir>` amplio](feedback_git_add_dir_cola_untracked.md) — cola untracked permanentes; stagear archivos explícitos.
- [tipo_tramite (catálogo) sin id_usuario_alta](reference_tipo_tramite_sin_usuario_alta.md) — la auditoría de usuario está solo en las INSTANCIAS.
- [GH Pages publica todo lo commiteado](reference_gh_pages_publica_todo_lo_commiteado.md) — preguntar antes de `git add` .md/.html.
- [FastAPI: dependencies del router no se anulan](reference_fastapi_router_dependencies_no_override.md) — `dependencies=[]` en el path NO cancela las del APIRouter.
- [Set-Content -Encoding utf8 mete BOM](feedback_set_content_utf8_bom.md) — rompe .env; usar Write/Edit o UTF8Encoding($false).
- [Mapeo alias SQL vs claves dict](feedback_mapeo_alias_sql_vs_claves_dict.md) — `**dict` sobre params de INSERT falla si las claves ≠ `:alias`.
- [SQLAlchemy CAST a uuid](feedback_sqlalchemy_cast_uuid.md) — `:token::uuid` parsea mal; usar `CAST(:token AS uuid)`.
- [Mantenimiento de CLAUDE.md y memorias](feedback_mantenimiento_doc_y_memorias.md) — separar bitácora de regla; checklist al cerrar.
- [Testear shell local + dist prod: 401 nukea sesion](feedback_token_local_contra_dist_prod_nuke_sesion.md) — sembrar sesion con token PROD (ambas shapes).
