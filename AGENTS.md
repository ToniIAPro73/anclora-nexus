
> [!IMPORTANT]
> This repository is governed by the Anclora canonical contracts under `.anclora/`.
> Agent-specific defaults, personal presets, or global agent configurations must NOT override those contracts.
> Read `.anclora/AGENT_PROJECT_CONTEXT.md` before starting substantial work.


# AGENTS.md — Constitución del Proyecto Anclora Nexus

Este archivo define las reglas duras, restricciones y criterios de validación para agentes de desarrollo en este proyecto. Estas reglas son **inmutables** durante la fase beta (Q1-Q2 2026).

---

<!-- MEMANTO-MANAGED-SECTION -->
## Uso de Memanto

Agente por defecto en este repo: `anclora-nexus`.

Usa Memanto como memoria operativa persistente. Sirve para recordar decisiones tecnicas, errores resueltos, contexto estable, preferencias del usuario y pendientes reales.

No sustituye documentacion canonica, Git, issues ni contratos de la boveda.

### Reglas

- Lee `MEMORY.md` antes de empezar.
- Si hay dudas sobre contexto previo, ejecuta `memanto recall` o `memanto answer` antes de asumir.
- Guarda solo informacion que ahorre tiempo o evite repetir errores.
- Todos los comandos `memanto` son comandos de shell. Ejecutalos en terminal.
- Nunca guardes secretos, tokens, contrasenas, credenciales completas ni datos personales sensibles.

### Inicio de tarea

```bash
memanto agent activate anclora-nexus
memanto recall "contexto actual de este proyecto" --limit 10
memanto answer "Que decisiones previas debo respetar aqui?"
```

### Durante la tarea

Guardar decision:

```bash
memanto remember "Decision: <que se decidio> porque <razon>. Afecta a <repo/modulo>." \
  --type decision \
  --confidence 0.95 \
  --provenance explicit_statement \
  --source codex-dev
```

Guardar error resuelto:

```bash
memanto remember "Error resuelto: <sintoma>. Causa: <causa>. Solucion: <solucion>. Verificado con <test/comando>." \
  --type error \
  --confidence 0.95 \
  --provenance observed \
  --source codex-dev
```

Guardar preferencia:

```bash
memanto remember "Preferencia: <preferencia concreta del usuario>." \
  --type preference \
  --confidence 1.0 \
  --provenance explicit_statement \
  --source codex-dev
```

Guardar pendiente:

```bash
memanto remember "Pendiente: <tarea>. Bloqueo: <bloqueo>. Siguiente paso: <accion>." \
  --type commitment \
  --confidence 0.9 \
  --provenance explicit_statement \
  --source codex-dev
```

### Cierre

```bash
memanto remember "Cierre: se completo <tarea>. Rama: <rama>. Commit: <sha>. Pendiente: <si/no>." \
  --type event \
  --confidence 0.95 \
  --provenance observed \
  --source codex-dev

memanto memory sync --project-dir .
```
<!-- /MEMANTO-MANAGED-SECTION -->

## Stack Tecnológico (NO cambiar sin aprobación explícita)

| Capa | Tecnología | Versión |
|------|-----------|---------|
| Frontend | Next.js (App Router) | 16.1.6 |
| UI Framework | React | 19.2.3 |
| Styling | Tailwind CSS | 4 |
| Components | Radix UI + shadcn/ui | Latest |
| State | Zustand | 5.0.11 |
| Auth | Supabase Auth Helpers | 0.15.0 |
| Backend | FastAPI + Uvicorn | Latest |
| Language | Python | 3.11+ |
| Agents | LangGraph | 0.3+ |
| LLM | Groq + Cloudflare Workers AI | Runtime profile |
| Database | Supabase PostgreSQL | Cloud |
| Typing | Pydantic v2 | Latest |

---

## Reglas de Código (Obligatorias)

### Seguridad

- **NUNCA** concatenar strings para construir queries SQL — usar queries parametrizadas siempre
- **NUNCA** incluir API keys, passwords o tokens en código fuente — solo en `.env` (nunca en git)
- `SUPABASE_SERVICE_ROLE_KEY`, `GROQ_API_KEY`, `CLOUDFLARE_API_TOKEN` e `INTERNAL_AUDIT_SECRET` solo en el backend (server-side)
- Prefijo `NEXT_PUBLIC_` solo para variables seguras de exponer en el cliente
- Sanitizar todo input de usuario antes de pasarlo a LLMs (prevención de prompt injection)

### Base de Datos

- **NUNCA** hacer UPDATE o DELETE sobre `audit_log` — es append-only e inmutable
- Todo acceso a datos debe filtrar por `org_id` (principio de aislamiento single-tenant)
- Nuevas tablas requieren migración SQL en `supabase/migrations/` con número secuencial
- Formato de archivo: `NNN_descripcion_snake_case.sql` (ej: `036_nueva_tabla.sql`)
- Las políticas RLS son obligatorias en todas las tablas con datos de usuario

### Backend

- Todo endpoint FastAPI que acceda a datos debe verificar `org_id` via `deps.py`
- Los modelos de request/response van en `backend/models/` como Pydantic schemas
- Cada router tiene su propio archivo en `backend/api/routes/`
- Los agentes LangGraph se invocan desde services, no directamente desde routes
- Máximo 50,000 tokens por ejecución de agente (límite constitucional)
- Máximo 60 minutos de duración por tarea de agente

### Frontend

- Dark mode obligatorio — NUNCA usar fondo blanco sin override explícito
- Paleta exclusiva: `#192350` (Navy), `#D4AF37` (Gold), `#AFD2FA` (Blue Light), `#F5F5F0` (White Soft)
- Iconos: Lucide React exclusivamente
- Fuentes: Inter (body) + Playfair Display (headings de lujo)
- Animaciones: Framer Motion (ya instalado)
- Todos los datos de Supabase via `@supabase/auth-helpers-nextjs`

### Agentes IA

- Todo output generado por IA debe incluir el identificador: `[Generado por Anclora Nexus Agent — {skill_name}]`
- Las ejecuciones de agentes se registran en `agent_logs` y `audit_log`
- La firma HMAC-SHA256 es obligatoria en cada entrada del `audit_log`
- Los límites de `constitutional_limits` (`max_daily_leads`, `max_llm_tokens_per_day`) son hard stops

---

## Estructura de Directorios (Respetar siempre)

```
anclora-nexus/
├── backend/
│   ├── agents/         ← LangGraph: graph.py, state.py, nodes/
│   ├── api/
│   │   ├── main.py     ← FastAPI app y registro de routers
│   │   ├── routes/     ← Un archivo por feature/router
│   │   └── deps.py     ← get_current_user(), get_org_id()
│   ├── models/         ← Pydantic schemas de request/response
│   ├── services/       ← Lógica de negocio (llama a Supabase)
│   └── skills/         ← Implementaciones Python de skills
├── frontend/
│   └── src/
│       ├── app/        ← Next.js App Router pages
│       ├── components/ ← Componentes React reutilizables
│       └── lib/        ← Supabase client, stores Zustand
├── supabase/
│   └── migrations/     ← SQL migrations numeradas secuencialmente
├── .agent/
│   ├── rules/          ← Reglas por feature (NO editar sin revisar)
│   └── skills/         ← Skills del sistema
├── architecture.md     ← Mapa de dependencias (mantener actualizado)
├── brain.md            ← ADN del negocio (ICP, métricas, territorio)
├── soul.md             ← Comportamiento del agente
└── AGENTS.md           ← Este archivo (reglas duras)
```

---

## Criterios de Validación Exitosa

Antes de marcar cualquier tarea como completada, verificar:

### Backend

- [ ] `GET /health` responde 200 OK
- [ ] Todas las queries filtran por `org_id`
- [ ] Nuevas columnas tienen migración SQL correspondiente
- [ ] No hay secrets hardcoded (buscar con grep)
- [ ] `audit_log` recibe entrada con firma HMAC en cada operación relevante

### Frontend

- [ ] No hay elementos blancos sin override en dark mode
- [ ] Los widgets del dashboard muestran datos reales (no mocks)
- [ ] Responsive: mobile, tablet, desktop verificados
- [ ] Los colores usan los tokens CSS de la paleta oficial

### Agentes

- [ ] El StateGraph compila sin errores
- [ ] `limit_check` bloquea correctamente cuando se alcanzan los límites
- [ ] Los outputs de IA incluyen el identificador obligatorio
- [ ] Las ejecuciones aparecen en `agent_logs`

### Seguridad

- [ ] Sin concatenación de strings en SQL
- [ ] Sin API keys en código
- [ ] Input sanitizado antes de pasar a LLM
- [ ] `audit_log` no admite UPDATE/DELETE (verificar con `REVOKE`)

---

## Principios de Diseño (Jerarquía de Documentos)

```
constitution-canonical.md  ← NORMA SUPREMA (gobernanza, seguridad, Golden Rules)
        ↓
product-spec-v0.md         ← ESPECIFICACIÓN DE PRODUCTO (user stories, skills, modelo datos)
        ↓
spec.md                    ← REFERENCIA TÉCNICA (arquitectura OpenClaw base)
        ↓
architecture.md            ← MAPA ACTUAL DEL CÓDIGO (mantener sincronizado)
```

En caso de conflicto entre documentos, prevalece el de mayor jerarquía.

---

## Restricciones del Scope v0

En v0 **NO implementar**:

- Multitenancy (org_id es fijo, single-tenant)
- Stripe o procesamiento de pagos
- MCP Docker sandbox (skills son módulos Python internos)
- MFA/WebAuthn (Supabase magic link es suficiente)
- Kill Switch multinivel (cancel simple desde UI)
- pgvector embeddings (diferido a v1)
- Lane Queue System (single-user, no hay concurrencia)

---

## Comandos de Desarrollo

```bash
# Frontend
cd frontend && npm run dev

# Backend
cd backend && python -m uvicorn api.main:app --reload --port 8000

# Supabase local
supabase start

# Tests Backend
cd backend && pytest

# Tests Frontend
cd frontend && npm test
```

---

## Notas para Codex

- El proyecto es un **monorepo NPM** con workspace en `frontend/`
- La documentación en `public/docs/` es estratégica, no técnica
- Los archivos en `.agent/` son la ubicación canónica activa para reglas y prompts de agentes. La carpeta `legacy/agent-systems/antigravity/` se conserva solo como histórico deprecated
- `sdd/` contiene los Software Design Documents por feature
- Antes de crear un nuevo archivo, verificar si ya existe algo similar
- Preferir editar código existente antes de crear nuevos archivos

<!-- ANCLORA-GLOBAL-AGENT-MEMORY-START -->
## Memoria global Anclora obligatoria

Antes de modificar este repositorio, todo agente IA debe leer:

1. `.anclora/global/GLOBAL_AGENT_WORKFLOW.md`, si existe
2. `.anclora/global/GLOBAL_GIT_WORKFLOW.md`, si existe
3. `.anclora/global/GLOBAL_SECURITY_RULES.md`, si existe
4. `.anclora/AGENT_PROJECT_CONTEXT.md`
5. `.anclora/GIT_WORKFLOW.md`
6. `.anclora/SECURITY_RULES.md`
7. `MEMORY.md`

Regla base: No trabajar directamente en `development`, `staging` ni `production`.
<!-- ANCLORA-GLOBAL-AGENT-MEMORY-END -->

<!-- ANCLORA-SDD-STANDARDS-START -->
## Metodología SDD — Estándar Unificado Anclora

Todo desarrollo en este repo sigue la metodología SDD unificada del ecosistema Anclora.

**Referencia canónica**: `agency-agents/docs/guides/SDD_INTEGRATION_GUIDE.md`
**Workflow OpenSpec**: `agency-agents/docs/guides/OPENSPEC_WORKFLOW.md`

### Flujo de trabajo Git

- Rama base de desarrollo: **`development`**
- Los agentes crean ramas desde `development`: `feat/<agente>-<descripcion>`, `fix/...`, `chore/...`
- Las ramas se mergean de vuelta a `development` via PR
- Promoción manual: `development → staging → production → main`
- Nunca commitear directamente en `main`, `staging` ni `production`

### Principios de desarrollo (Specboot)

1. **Small Tasks, One at a Time** — baby steps, nunca saltarse pasos
2. **Test-Driven Development** — escribir tests fallidos antes de implementar
3. **Type Safety** — código completamente tipado (TypeScript)
4. **Clear Naming** — variables y funciones descriptivas
5. **English Only** — código, comentarios y docs técnicos en inglés
6. **90% Test Coverage** — cobertura exhaustiva en todas las capas
7. **Incremental Changes** — modificaciones focalizadas y revisables

### Ciclo de cambios (SDD en este repo)

Toda feature o fix sigue este flujo antes de escribir código:

- Crear spec: `sdd/features/<nombre>/<nombre>-spec-v1.md`
- Crear plan: `sdd/features/<nombre>/<nombre>-plan-v1.md` (cambios complejos)
- Crear tasks: `sdd/features/<nombre>/<nombre>-tasks-v1.md`
- Implementar tarea a tarea (tests primero)
- Validar contra criterios de aceptación de la spec
- PR contra `development`, con referencia a la spec

### Reglas obligatorias

- **No spec, no code**: toda feature empieza con spec en `sdd/features/`
- **Tests primero**: el agente ejecuta los tests, nunca el usuario
- **Hermes gate**: cambio que afecta copy público → Hermes Copy Curator antes del merge
- **Spec inmutable**: una spec cerrada no se edita; los cambios generan una spec nueva
<!-- ANCLORA-SDD-STANDARDS-END -->
