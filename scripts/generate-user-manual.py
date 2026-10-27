#!/usr/bin/env python3
"""
Generate User Manual for Anclora Nexus
Based on ANCLORA-UMG-001 specification

Generates both Markdown (.md) and DOCX (.docx) formats
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path

# Read analysis file
ANALYSIS_PATH = "/tmp/anclora-nexus-development-analysis.md"

def generate_manual():
    """Generate complete user manual"""

    manual_content = f"""---
title: Manual de Usuario: Anclora Nexus
version: 1.2.3
date: {datetime.now().strftime("%Y-%m-%d")}
language: es
status: current
---

# Manual de Usuario: Anclora Nexus

**Versión 1.2.3 | {datetime.now().strftime("%d de %B de %Y")}**

---

## Tabla de Contenidos

1. [Introducción](#introducción)
2. [Navegación Principal](#navegación-principal)
3. [Sección CORE](#sección-core)
4. [Sección INTELLIGENCE](#sección-intelligence)
5. [Sección OPERATIONS](#sección-operations)
6. [Casos de Uso Prácticos](#casos-de-uso-prácticos)
7. [Troubleshooting](#troubleshooting)

---

## 1. Introducción

### 1.1 Qué es Anclora Nexus

Anclora Nexus es un CRM inmobiliario inteligente diseñado específicamente para **Anclora Private Estates** por eXp Realty Spain. El sistema combina gestión tradicional de leads y propiedades con inteligencia artificial territorial para optimizar la captación de vendedores y el matching con compradores en el suroeste de Mallorca.

**Características principales:**
- **Seller Pipeline:** Motor de adquisición de vendedores con detección de FSBOs y propiedades estancadas
- **Intelligence Territorial:** Integración con NotebookLM para insights de mercado en tiempo real
- **Prospection Matching:** Algoritmo explicable de matching comprador-propiedad
- **Observabilidad Operativa:** Command Center ejecutivo con métricas de negocio y governance de costos

**Filosofía del sistema:**
> "Cada hora invertida debe acortar el camino al siguiente mandato."

### 1.2 Requisitos Previos

**Técnicos:**
- Navegador actualizado (Chrome 90+, Firefox 88+, Safari 14+, Edge 90+)
- Conexión a internet estable
- Resolución mínima: 1280x720px (recomendada: 1920x1080px)

**Organizativos:**
- Cuenta de usuario activa en Anclora Identity
- Membresía activa en una organización
- Rol asignado: `owner`, `manager` o `agent`

**URL de acceso:**
- Desarrollo: `http://localhost:3000`
- Producción: `https://app.anclora.com` (pendiente despliegue)

### 1.3 Acceso a la Plataforma

#### Inicio de Sesión

1. Abre la URL de la aplicación
2. Introduce tu **email** registrado
3. Introduce tu **contraseña**
4. Pulsa **Iniciar sesión**
5. Si las credenciales son correctas y tu membresía está activa, serás redirigido al dashboard

#### Primer Acceso (Invitación)

1. Recibirás un email de invitación del Owner
2. Haz clic en el enlace de invitación
3. Completa el registro con email y contraseña
4. Verifica tu email si es requerido
5. Inicia sesión con tus credenciales

#### Recuperación de Contraseña

1. En la pantalla de login, pulsa **Olvidé mi contraseña**
2. Introduce tu email
3. Recibirás un enlace de recuperación
4. Sigue el enlace y establece una nueva contraseña
5. Inicia sesión con la nueva contraseña

---

## 2. Navegación Principal

Anclora Nexus se organiza en dos componentes principales de navegación:

### 2.1 Sidebar (Menú Lateral)

El sidebar izquierdo contiene **3 secciones colapsables** con un total de **17 opciones de menú**.

#### Sección CORE (Core Business)

**Propósito:** Gestión operativa diaria del negocio inmobiliario.

| Opción | Ruta | Descripción |
|--------|------|-------------|
| **Dashboard** | `/dashboard` | Panel principal con widgets operativos |
| **Leads** | `/leads` | Gestión de contactos entrantes y pipeline |
| **Properties** | `/properties` | Inventario de propiedades |
| **Tasks** | `/tasks` | Sistema de tareas y seguimientos |
| **Team** | `/team` | Gestión de miembros y roles de la organización |

#### Sección INTELLIGENCE (Intelligence & Prospection)

**Propósito:** Prospección inteligente y captación de vendedores.

| Opción | Ruta | Descripción |
|--------|------|-------------|
| **Prospection studio** | `/prospection` | Prospección legacy (deprecated) |
| **Prospection operativa** | `/prospection-unified` | Cola de trabajo unificada de prospección |
| **Seller Pipeline** | `/sellers` | Motor de adquisición de vendedores (FSBOs, stagnant) |
| **Opportunity Ranking** | `/opportunity-ranking` | Ranking explicable de oportunidades |
| **Intelligence** | `/intelligence` | Centro de control con chat y análisis territorial |

#### Sección OPERATIONS (Operations & Tools)

**Propósito:** Herramientas operativas y observabilidad.

| Opción | Ruta | Descripción |
|--------|------|-------------|
| **Ingestion** | `/ingestion` | Ingesta unificada de datos seller-side |
| **Data Quality** | `/data-quality` | Calidad de datos y resolución de entidades |
| **Feed Orchestrator** | `/feed-orchestrator` | Publicación multicanal (Idealista, Fotocasa) |
| **Automation & Alerting** | `/automation-alerting` | Automatización con guardarraíles HITL |
| **Command Center** | `/command-center` | KPIs ejecutivos y métricas de negocio |
| **Deal Margin Simulator** | `/deal-margin-simulator` | Simulador de margen por operación |
| **Source Observatory** | `/source-observatory` | Performance de fuentes de leads |

### 2.2 Header (Barra Superior)

El header superior contiene **6 componentes** funcionales:

| Componente | Icono | Función |
|------------|-------|---------|
| **Search** | 🔍 | Búsqueda global en leads, propiedades y tareas |
| **Notifications** | 🔔 | Panel de notificaciones y alertas del sistema |
| **Currency Selector** | 💱 | Selección de moneda (EUR, USD, GBP) |
| **Language Selector** | 🌐 | Selección de idioma (ES, EN, DE, RU) |
| **Unit Selector** | 📏 | Sistema de unidades (m², sqft) |
| **User Menu** | 👤 | Perfil, configuración y logout |

---

## 3. Sección CORE

### 3.1 Dashboard

**Ruta:** `/dashboard`
**Acceso:** Owner, Manager, Agent

#### Propósito

El Dashboard es tu **centro de comando diario**. En una sola pantalla, obtienes visibilidad completa de:
- Métricas clave de negocio
- Leads recientes y priorizados
- Tareas del día
- Estado del pipeline de propiedades
- Actividad de agentes automáticos
- Acceso rápido a acciones críticas

#### Widgets Principales

##### A) QuickStats

**Qué muestra:**
- Leads totales esta semana
- Tareas completadas hoy
- Propiedades activas
- Tasa de conversión

**Para qué sirve:**
Validar en 10 segundos si estás por encima o por debajo de la carga esperada.

**Cómo usarlo:**
- Compara la tendencia con tu referencia semanal
- Si ves caída de actividad, prioriza prospección
- Si ves pico de leads, ajusta carga de equipo

##### B) LeadsPulse

**Qué muestra:**
- Últimos 5-10 leads entrantes
- Prioridad por lead (1-5, siendo 5 = Whale)
- Estado actual (nuevo, contactado, cualificado)
- Tiempo desde entrada

**Para qué sirve:**
Decidir rápidamente qué lead tocar primero.

**Cómo usarlo:**
1. Identifica leads con prioridad 4-5
2. Revisa tiempo desde entrada (objetivo < 15 min para P5)
3. Haz clic en el lead para abrir detalle
4. Registra contacto inmediatamente

**Buenas prácticas:**
- Leads P5 (Whale): responder < 15 minutos
- Leads P4: responder < 2 horas
- Leads P3: responder < 24 horas

##### C) TasksToday

**Qué muestra:**
- Tareas del día (vencidas + hoy)
- Tareas asignadas a ti
- Estado (pendiente, en progreso, completada)

**Para qué sirve:**
Evitar que se acumulen seguimientos pendientes.

**Cómo usarlo:**
1. Ordena mentalmente por impacto comercial (no por facilidad)
2. Completa tareas críticas primero
3. Reprograma tareas no críticas con criterio explícito
4. Marca como completada con notas del resultado

##### D) PropertyPipeline

**Qué muestra:**
- Distribución de propiedades por etapa:
  - Nueva
  - Valoración
  - Listada
  - Under Offer
  - Sold
  - Lost

**Para qué sirve:**
Identificar cuellos de botella en el pipeline.

**Cómo usarlo:**
1. Identifica la etapa más saturada
2. Abre propiedades estancadas en esa etapa
3. Define acción concreta para desbloquear
4. Si hay muchas en "Valoración", prioriza CMAs
5. Si hay muchas en "Listada" sin movimiento, revisa precio/marketing

##### E) AgentStream

**Qué muestra:**
- Últimas ejecuciones de agentes IA
- Skill ejecutado (lead_intake, prospection_weekly, recap_weekly)
- Estado (success, failed)
- Timestamp

**Para qué sirve:**
Trazabilidad operativa de automatizaciones.

**Cómo usarlo:**
1. Confirma que flujos esperados se ejecutaron (ej: prospection_weekly cada domingo)
2. Si ves `failed`, haz clic para ver detalle del error
3. Reporta errores repetidos al Tech Lead

##### F) QuickActions

**Qué muestra:**
- Botones de acceso rápido:
  - Crear lead
  - Crear tarea
  - Crear propiedad
  - Ejecutar skill manual

**Para qué sirve:**
Reducir fricción en acciones frecuentes.

**Cómo usarlo:**
- Usa estos botones en vez de navegar a cada módulo
- Formularios modales se abren in-place
- Guarda y continúa trabajando sin perder contexto

##### G) BudgetStatusWidget

**Qué muestra:**
- Presupuesto mensual LLM (tokens/€)
- Consumo actual
- % utilizado
- Días restantes del mes

**Para qué sirve:**
Governance de costos para evitar sobregasto.

**Cómo usarlo:**
- Si estás cerca del 80%, modera ejecuciones de agentes
- Si superas el 100%, el sistema bloquea automáticamente (hard stop)
- Contacta al Owner para ajustar presupuesto si es necesario

##### H) RadarTerritorial

**Qué muestra:**
- Insights de NotebookLM por zona:
  - Andratx, Calvià, Son Ferrer, Santa Ponça, Paguera
- Oportunidades activas detectadas
- Señales de mercado

**Para qué sirve:**
Contexto territorial para prospección informada.

**Cómo usarlo:**
1. Revisa las 3 oportunidades prioritarias
2. Haz clic en zona para ver detalle completo
3. Usa estos insights en tu copy de captación
4. Refresca datos con sync territorial semanal

#### Rutina Diaria Recomendada (15-20 min)

**Secuencia:**
1. **QuickStats:** Validar pulso general
2. **LeadsPulse:** Seleccionar top 3 leads
3. **TasksToday:** Resolver pendientes críticos
4. **PropertyPipeline:** Desbloquear etapa más atascada
5. **RadarTerritorial:** Actualizar contexto de mercado
6. **QuickActions:** Ejecutar acción de mayor impacto

### 3.2 Leads

**Ruta:** `/leads`
**Acceso:** Owner, Manager, Agent

#### Propósito

Gestión completa del ciclo de vida de leads entrantes, desde captura hasta conversión.

#### Funcionalidad Principal

**Tabla de Leads:**
- Filtros: estado, prioridad, fuente, fecha
- Columnas: nombre, email, presupuesto, estado, prioridad, última interacción
- Acciones: editar, cambiar estado, crear tarea, marcar como ganado/perdido

**Detalle de Lead (Modal):**
- Datos de contacto completos
- Historial de interacciones
- Notas privadas
- Propiedades vinculadas
- Tareas asociadas

**Estados de Lead:**
- **Nuevo:** Recién ingresado, sin contactar
- **Contactado:** Primera interacción realizada
- **Cualificado:** Potencial confirmado
- **Propuesta:** Oferta comercial enviada
- **Ganado:** Convertido en cliente
- **Perdido:** Descartado (con motivo registrado)

#### Cómo Usarlo

**Caso: Lead nuevo entra por formulario web**

1. El lead aparece en **LeadsPulse** (Dashboard) con estado "Nuevo"
2. Recibes notificación si tienes alertas habilitadas
3. Abre el lead desde Dashboard o desde `/leads`
4. Revisa datos: presupuesto, zona de interés, urgencia
5. Llama o envía email (registra la interacción)
6. Actualiza estado a "Contactado"
7. Crea tarea de seguimiento (ej: "Enviar propuestas en 2 días")
8. Vincula propiedades que encajen con su perfil

**Caso: Cualificar lead contactado**

1. Filtra leads por estado "Contactado"
2. Abre detalle de cada uno
3. Verifica que:
   - Presupuesto es realista
   - Zona de interés está en tu scope
   - Timing de compra es < 6 meses
4. Si cumple criterios, cambia a "Cualificado"
5. Si no cumple, cambia a "Perdido" y registra motivo

**Buenas Prácticas:**
- No dejes leads en "Nuevo" > 24h
- Registra todas las interacciones (call, email, visita)
- Usa notas privadas para contexto importante
- Actualiza prioridad si cambia situación del lead

### 3.3 Properties

**Ruta:** `/properties`
**Acceso:** Owner, Manager, Agent

#### Propósito

Gestión del inventario de propiedades disponibles para venta o alquiler.

#### Funcionalidad Principal

**Tabla de Propiedades:**
- Filtros: zona, tipo, precio, estado
- Columnas: dirección, precio, m², tipo, estado, origen
- Acciones: editar, cambiar estado, publicar feed, ver historial

**Detalle de Propiedad (Modal):**
- Datos técnicos (m², habitaciones, baños)
- Fotos y documentación
- Historial de cambios de precio
- Valoración AI (si disponible)
- Estado de publicación en portales

**Estados de Propiedad:**
- **Nueva:** Recién captada
- **Valoración:** En proceso de CMA
- **Listada:** Publicada activamente
- **Under Offer:** Con oferta recibida
- **Sold:** Vendida
- **Lost:** Perdida (mandato cancelado, vendida por otro)

#### Cómo Usarlo

**Caso: Captar nueva propiedad**

1. Entra a `/properties`
2. Pulsa **Nueva Propiedad**
3. Completa formulario:
   - Dirección completa
   - Zona (ej: Andratx, Calvià)
   - Tipo (villa, apartamento, terreno)
   - Precio inicial
   - M² útiles y construidos
   - Habitaciones, baños
4. Sube fotos (mínimo 5, recomendado 15+)
5. Indica origen (captación propia, StateFox, otro)
6. Guarda como "Nueva"
7. El sistema asigna ID único

**Caso: Valorar y listar propiedad**

1. Abre propiedad en estado "Nueva"
2. Ejecuta CMA (Comparative Market Analysis):
   - Usa datos de RadarTerritorial para contexto
   - Compara con propiedades similares en zona
   - Valida precio con Owner si es necesario
3. Ajusta precio si es necesario
4. Cambia estado a "Listada"
5. Publica en portales via Feed Orchestrator
6. Crea tarea de seguimiento para monitorear visitas

**Caso: Gestionar oferta**

1. Cuando recibes oferta, cambia estado a "Under Offer"
2. Registra detalles de la oferta en notas
3. Coordina con comprador y vendedor
4. Si se acepta y cierra, cambia a "Sold"
5. Si se cancela, vuelve a "Listada"

### 3.4 Tasks

**Ruta:** `/tasks`
**Acceso:** Owner, Manager, Agent

#### Propósito

Sistema de gestión de tareas para seguimientos comerciales y operativos.

#### Funcionalidad Principal

**Tabla de Tareas:**
- Filtros: estado, asignado a, fecha vencimiento, prioridad
- Columnas: título, descripción, lead/propiedad asociada, estado, fecha
- Acciones: marcar completada, reprogramar, editar, eliminar

**Crear Tarea:**
- Título (obligatorio)
- Descripción
- Fecha vencimiento
- Prioridad (low, medium, high)
- Asignar a (si eres Owner/Manager)
- Vincular con lead o propiedad

**Estados de Tarea:**
- **Pending:** Sin empezar
- **In Progress:** En ejecución
- **Completed:** Completada
- **Cancelled:** Cancelada

#### Cómo Usarlo

**Caso: Crear tarea de seguimiento de lead**

1. Desde detalle de lead, pulsa **Crear Tarea**
2. Título: "Llamar a Ana García - seguimiento propuesta"
3. Descripción: "Enviar propuestas villas Andratx 800-1M€"
4. Fecha: Dentro de 2 días
5. Prioridad: High
6. Guarda
7. La tarea aparece en TasksToday cuando llegue la fecha

**Caso: Completar tarea del día**

1. Abre Dashboard y revisa TasksToday
2. Haz clic en la tarea
3. Ejecuta la acción (llamada, email, etc.)
4. Registra resultado en notas
5. Marca como "Completed"
6. Si surge nueva acción, crea nueva tarea

**Caso: Reprogramar tarea**

1. Si no puedes completar una tarea hoy
2. Abre la tarea
3. Pulsa **Editar**
4. Ajusta fecha vencimiento
5. Añade nota explicando por qué se reprograma
6. Guarda

**Buenas Prácticas:**
- Sé específico en el título (no "Llamar lead" sino "Llamar Ana García - seguimiento propuesta")
- Vincula siempre con lead o propiedad
- No acumules tareas vencidas (completa o reprograma con criterio)
- Usa prioridades correctamente (no todo es High)

### 3.5 Team

**Ruta:** `/team`
**Acceso:** Owner (full), Manager (read-only)

#### Propósito

Gestión de miembros de la organización, roles y permisos.

#### Funcionalidad Principal

**Tabla de Miembros:**
- Columnas: nombre, email, rol, estado, fecha invitación
- Acciones (Owner): invitar, cambiar rol, suspender, eliminar

**Roles Disponibles:**

| Rol | Permisos |
|-----|----------|
| **Owner** | Control total: gestión de equipo, configuración org, acceso a todo |
| **Manager** | Gestión operativa: leads, propiedades, tareas, visualización de métricas |
| **Agent** | Ejecución: leads asignados, tareas propias, propiedades (solo lectura) |

**Estados de Membresía:**
- **Active:** Operativo, puede iniciar sesión
- **Pending:** Invitado, pendiente de aceptar
- **Suspended:** Bloqueado temporalmente
- **Removed:** Fuera de la organización

#### Cómo Usarlo (Owner)

**Caso: Invitar nuevo miembro**

1. Entra a `/team`
2. Pulsa **Invitar Miembro**
3. Introduce email del nuevo miembro
4. Selecciona rol (Agent por defecto)
5. Pulsa **Enviar Invitación**
6. El miembro recibe email con enlace
7. Aparece en tabla con estado "Pending"
8. Cuando acepte, pasa a "Active"

**Caso: Cambiar rol de miembro**

1. Localiza el miembro en la tabla
2. Pulsa **Editar**
3. Selecciona nuevo rol
4. Confirma el cambio
5. El miembro verá cambios al recargar sesión

**Caso: Suspender cuenta**

1. Si un miembro necesita acceso temporal bloqueado
2. Pulsa **Suspender** en su fila
3. Confirma acción
4. Estado cambia a "Suspended"
5. El miembro no podrá iniciar sesión
6. Para reactivar, pulsa **Reactivar**

**Buenas Prácticas:**
- Asigna el rol mínimo necesario (principio de privilegio mínimo)
- Revisa periódicamente membresías "Pending" antiguas
- Documenta motivo al suspender/eliminar miembros
- Mantén siempre al menos 1 Owner activo

---

## 4. Sección INTELLIGENCE

### 4.1 Prospection studio (Legacy)

**Ruta:** `/prospection`
**Acceso:** Owner, Manager
**Estado:** Deprecated - Usar Prospection operativa

### 4.2 Prospection operativa

**Ruta:** `/prospection-unified`
**Acceso:** Owner, Manager, Agent

#### Propósito

**Cola de trabajo unificada** para prospección buyer-side: matching, seguimiento y cierre.

#### Funcionalidad Principal

**Tres Colas de Trabajo:**

1. **Cola de Cierre**
   - Matches con score alto (70-100)
   - Priorizados para contacto inmediato
   - Estados: candidate → contacted → viewing → negotiating → offer → closed

2. **Captación Prioritaria**
   - Propiedades con high-ticket score > 75
   - Pendientes de match con buyers
   - Requieren enriquecimiento de datos

3. **Seguimiento de Buyers**
   - Buyers activos con motivation score > 60
   - Pendientes de match con properties
   - Requieren actualización de criterios

**Matching Score Explicable:**
- 35% ajuste de presupuesto
- 25% ajuste de zona
- 20% ajuste de tipología
- 10% timing de compra
- 10% motivación

#### Cómo Usarlo

**Caso: Trabajar cola de cierre**

1. Entra a `/prospection-unified`
2. Revisa matches con score > 80
3. Ordena por score descendente
4. Para cada match:
   - Abre detalle (buyer + property)
   - Verifica encaje real (más allá del score)
   - Contacta buyer si procede
   - Registra actividad
   - Mueve a siguiente estado del pipeline
5. Marca match como "contacted"
6. Crea tarea de seguimiento

**Caso: Avanzar match por pipeline**

Estados del pipeline de prospection:
- **Candidate:** Match detectado, sin contacto
- **Contacted:** Buyer contactado, presentada propiedad
- **Viewing:** Visita programada o realizada
- **Negotiating:** Oferta en negociación
- **Offer:** Oferta formal presentada
- **Closed:** Operación cerrada (éxito)
- **Dropped:** Match descartado (motivo registrado)

Acciones por estado:
1. **Candidate → Contacted:**
   - Llama/email al buyer
   - Presenta la propiedad matched
   - Registra resultado del contacto

2. **Contacted → Viewing:**
   - Buyer muestra interés
   - Programa visita
   - Registra fecha/hora

3. **Viewing → Negotiating:**
   - Visita realizada, feedback positivo
   - Buyer quiere hacer oferta
   - Inicia negociación

4. **Negotiating → Offer:**
   - Términos acordados
   - Oferta formal presentada por escrito

5. **Offer → Closed:**
   - Oferta aceptada
   - Contrato firmado
   - Operación cerrada

### 4.3 Seller Pipeline

**Ruta:** `/sellers`
**Acceso:** Owner, Manager, Agent

#### Propósito

**Motor de adquisición de vendedores** mediante detección inteligente de FSBOs, propiedades estancadas y señales de motivación de venta.

#### Funcionalidad Principal

**Tabla de Sellers:**
- Columnas: nombre/empresa, propiedad, zona, precio, prioridad, estado, fuente
- Filtros: zona, estado, prioridad (1-5), fuente
- Acciones: ver detalle, cambiar estado, crear interacción, generar dossier

**Prioridades de Seller:**
- **P5 (Whale):** Alto valor + alta urgencia → mandato casi seguro
- **P4:** Alto potencial → seguimiento intensivo
- **P3:** Potencial medio → nutrición activa
- **P2:** Potencial bajo → seguimiento pasivo
- **P1:** Frío → backlog

**Estados de Seller:**
- **Detected:** Recién detectado por fuente (StateFox, scraping)
- **Contacted:** Primer contacto realizado
- **Qualified:** Verificado potencial real
- **Proposal:** Propuesta de mandato enviada
- **Mandate:** Mandato exclusivo firmado
- **Lost:** Oportunidad perdida

**Fuentes de Sellers:**
- **StateFox Telegram:** Capturas desde canal Telegram
- **StateFox Discovery:** Análisis de conversaciones Telegram
- **FSBO Scraper:** Portales inmobiliarios
- **Manual:** Ingreso manual del equipo

#### Cómo Usarlo

**Caso: Revisar nuevos sellers detectados**

1. Entra a `/sellers`
2. Filtra por estado "Detected"
3. Ordena por prioridad descendente (P5 primero)
4. Para cada seller P5:
   - Abre detalle
   - Revisa datos de propiedad
   - Lee contexto de detección
   - Valida señales de motivación
   - Si procede, marca como "Contacted" y llama inmediatamente

**Caso: Contactar seller prioritario**

1. Seller P5 o P4 en estado "Detected"
2. Abre drawer de detalle
3. Revisa:
   - Propiedad (precio, zona, tipo, estado)
   - Señales de motivación (días en mercado, precio vs CMA)
   - Canales de contacto disponibles (email, teléfono, WhatsApp)
4. Prepara copy de captación usando insights de RadarTerritorial
5. Contacta por canal preferente
6. Registra interacción:
   - Canal usado
   - Resultado (interesado, rechazó, sin respuesta)
   - Notas relevantes
7. Cambia estado según resultado:
   - Si interesado → "Qualified"
   - Si rechaza → "Lost"
   - Si sin respuesta → mantener "Contacted", crear tarea seguimiento

**Caso: Proponer mandato**

1. Seller en estado "Qualified"
2. Has validado:
   - Propiedad real y verificable
   - Motivación genuina de venta
   - Precio realista (o ajustable)
3. Genera dossier de captación:
   - Usa widget "Whale Dossier" en detalle
   - Incluye CMA de zona
   - Incluye propuesta de valor eXp
4. Envía propuesta de mandato exclusivo
5. Cambia estado a "Proposal"
6. Crea tarea de seguimiento a 3-5 días

**Caso: Firmar mandato**

1. Seller acepta propuesta
2. Coordina firma de mandato
3. Cambia estado a "Mandate"
4. Crea propiedad correspondiente en `/properties`
5. Vincula seller con propiedad
6. Celebra el éxito 🎉

**Memoria Semántica del Seller:**

Cada seller P5 (Whale) tiene memoria semántica que registra:
- Todas las interacciones
- Contexto de conversaciones
- Objeciones y respuestas
- Evolución de la relación

Para usar la memoria:
1. Abre drawer de seller
2. Ve a pestaña "Memoria"
3. Haz query: "¿Cuáles fueron sus objeciones principales?"
4. El sistema te devuelve contexto relevante
5. Usa esto para personalizar siguiente interacción

### 4.4 Opportunity Ranking

**Ruta:** `/opportunity-ranking`
**Acceso:** Owner, Manager

#### Propósito

Ranking explicable de todas las oportunidades activas (leads, sellers, matches) priorizadas por scoring IA.

#### Funcionalidad Principal

**Tabla de Oportunidades:**
- Columnas: tipo (lead/seller/match), nombre, score, breakdown, estado, acción recomendada
- Filtros: tipo, score mínimo, estado
- Scoring explicable con breakdown visual

**Tipos de Oportunidades:**
1. **Leads:** Score de conversión (presupuesto + zona + timing + motivación)
2. **Sellers:** Score de captación (valor propiedad + urgencia + zona + fuente)
3. **Matches:** Score de cierre (ajuste buyer-property)

#### Cómo Usarlo

1. Entra a `/opportunity-ranking`
2. Revisa top 10 oportunidades
3. Para cada una, verifica breakdown del score
4. Ejecuta acción recomendada
5. Usa este ranking para priorizar tu día

**Ejemplo de Breakdown:**

Seller "Villa Andratx - Calle Mar":
- Score total: 87/100
- Breakdown:
  - Valor propiedad (€1.2M): 35/35 ✓
  - Urgencia (120 días en mercado): 23/25 ✓
  - Zona premium (Andratx): 20/25 ✓
  - Fuente (StateFox Telegram): 9/15 ⚠️

Acción recomendada: **Contactar hoy - alta probabilidad de mandato**

### 4.5 Intelligence

**Ruta:** `/intelligence`
**Acceso:** Owner, Manager

#### Propósito

**Centro de control de Intelligence** con chat conversacional, análisis territorial y status de sync pack NotebookLM.

#### Componentes Principales

**1. Chat Console**
- Chat conversacional con el orchestrator
- Acepta queries en lenguaje natural
- Ejemplos:
  - "¿Cuántos sellers P5 tenemos en Andratx?"
  - "Dame un resumen de actividad de esta semana"
  - "¿Qué oportunidades hay en Son Ferrer?"

**2. Decision Console**
- Visualización de decisiones del Governor
- Muestra lógica de routing
- Útil para debugging y transparencia

**3. Query Plan Panel**
- Plan de query del Router
- Muestra qué fuentes se consultan
- Tiempo estimado de ejecución

**4. Territorial Sync Status Card**
- Estado del sync pack NotebookLM
- Última sincronización
- Próxima sincronización programada
- Coverage territorial (zonas activas)

**5. StateFox Discovery Card**
- Último discovery ejecutado
- Sellers detectados
- Señales activas

#### Subpáginas

**Intelligence / StateFox Bridge**

**Ruta:** `/intelligence/statefox-bridge`
**Propósito:** Puente para importar listings desde Telegram StateFox.

**Funcionalidad:**
1. Pega raw text capturado de Telegram
2. El sistema parsea:
   - Precio
   - Zona
   - Tipo de propiedad
   - Contacto
3. Valida estructura
4. Importa como seller en estado "Detected"

**Cómo usarlo:**
1. Copia mensaje de Telegram StateFox
2. Entra a `/intelligence/statefox-bridge`
3. Pega en el textarea
4. Pulsa **Parse & Import**
5. Revisa preview
6. Confirma import
7. El seller aparece en `/sellers`

**Intelligence / StateFox Discovery**

**Ruta:** `/intelligence/statefox-discovery`
**Propósito:** Análisis automático de conversaciones Telegram para detectar sellers.

**Funcionalidad:**
- Discovery automático programado (cada 6h)
- Análisis de patrones de conversación
- Detección de señales de venta
- Scoring de urgencia

**Cómo usarlo:**
1. Entra a `/intelligence/statefox-discovery`
2. Revisa último discovery ejecutado
3. Ve lista de sellers detectados
4. Para cada seller:
   - Lee contexto de detección
   - Valida si es señal genuina
   - Importa a sellers si procede

---

## 5. Sección OPERATIONS

### 5.1 Ingestion

**Ruta:** `/ingestion`
**Acceso:** Owner, Manager

#### Propósito

**Ingesta unificada seller-side** desde múltiples fuentes con contrato canónico y dedupe automático.

#### Funcionalidad Principal

**Eventos de Ingesta:**
- Tabla de eventos procesados
- Columnas: timestamp, fuente, entity_type (seller_signal), status, dedupe_key
- Estados: pending, processed, failed, duplicated

**Conectores Disponibles:**
- StateFox Telegram
- StateFox Live Capture
- FSBO Scraper (Idealista, Fotocasa)
- Manual import

#### Cómo Usarlo

1. Los eventos se procesan automáticamente
2. Revisa esta pantalla para observabilidad
3. Filtra por estado "failed" para ver errores
4. Filtra por estado "duplicated" para ver dedupe en acción

### 5.2 Data Quality

**Ruta:** `/data-quality`
**Acceso:** Owner, Manager

#### Propósito

**Calidad de datos y resolución de entidades** mediante detección de duplicados con scoring explicable.

#### Funcionalidad Principal

**Métricas de Calidad:**
- % de registros con email válido
- % de registros con teléfono válido
- % de duplicados detectados
- % de duplicados resueltos

**Candidatos de Duplicados:**
- Pares de registros sospechosos
- Score de similitud (0-100)
- Breakdown: email match, teléfono match, nombre fuzzy match
- Acción: merge (fusionar) o keep both (mantener separados)

#### Cómo Usarlo

1. Entra a `/data-quality`
2. Revisa métricas globales
3. Ve a sección "Candidatos de Duplicados"
4. Para cada par:
   - Revisa datos de ambos registros
   - Verifica score de similitud
   - Si son duplicados reales, pulsa **Merge**
   - Si son distintos, pulsa **Keep Both**
5. Al hacer merge:
   - Selecciona registro master (el que se queda)
   - Datos del otro se fusionan
   - Referencias se actualizan

### 5.3 Feed Orchestrator

**Ruta:** `/feed-orchestrator`
**Acceso:** Owner, Manager

#### Propósito

**Publicación multicanal** de propiedades en portales inmobiliarios (Idealista, Fotocasa, etc.) con validación previa.

#### Funcionalidad Principal

**Channels Configurados:**
- Idealista
- Fotocasa
- (Extensible a más portales)

**Validación de Feeds:**
- Campos obligatorios completos
- Fotos mínimas (5+)
- Precio dentro de rango razonable
- Descripción > 100 caracteres

**Runs de Publicación:**
- Historial de ejecuciones
- Estado: success, partial, failed
- Propiedades publicadas
- Issues encontrados

#### Cómo Usarlo

**Caso: Publicar propiedad en Idealista**

1. Asegúrate de que la propiedad en `/properties` está:
   - Completa (todos los campos)
   - Con fotos (mínimo 5)
   - Con descripción profesional
2. Entra a `/feed-orchestrator`
3. Selecciona channel "Idealista"
4. Pulsa **Validate**
5. Revisa issues (si hay)
6. Corrige issues en `/properties`
7. Pulsa **Publish**
8. Verifica en "Runs" que status = success

### 5.4 Automation & Alerting

**Ruta:** `/automation-alerting`
**Acceso:** Owner

#### Propósito

**Automatización con guardarraíles HITL** (Human-In-The-Loop) y sistema de alertas operacionales.

#### Funcionalidad Principal

**Reglas de Automatización:**
- Trigger: evento del sistema
- Condition: criterios a cumplir
- Action: acción a ejecutar
- HITL checkpoint: revisión humana obligatoria antes de acción crítica

**Alertas Operacionales:**
- Budget > 80% consumido
- Cron territorial no ejecutado en 48h
- Scraping sin cobertura
- Tasa de error > 10% en skill

#### Cómo Usarlo

**Caso: Crear regla de automatización**

1. Entra a `/automation-alerting`
2. Pulsa **Nueva Regla**
3. Configura:
   - Trigger: "Nuevo seller P5 detectado"
   - Condition: "Zona = Andratx AND Precio > €800k"
   - Action: "Crear tarea urgente asignada a Owner"
   - HITL: "Requerir aprobación antes de contactar"
4. Guarda regla
5. La próxima vez que se detecte un seller que cumpla, se ejecuta

**Caso: Revisar alertas activas**

1. Entra a `/automation-alerting`
2. Ve sección "Alertas Activas"
3. Para cada alerta:
   - Lee detalle
   - Pulsa **Acknowledge** si ya lo sabes
   - Pulsa **Resolve** si lo solucionaste
4. Alertas críticas no se pueden ignorar hasta resolver

### 5.5 Command Center

**Ruta:** `/command-center`
**Acceso:** Owner

#### Propósito

**KPIs ejecutivos y métricas de negocio** en un dashboard de alto nivel para toma de decisiones estratégicas.

#### Funcionalidad Principal

**Snapshot Ejecutivo:**
- Leads: total, tasa conversión, pipeline value
- Sellers: total, P5 activos, mandatos firmados este mes
- Properties: inventario, bajo oferta, vendidas este mes
- Matches: activos, tasa cierre, comisión estimada

**Trends Históricos:**
- Gráficos de tendencia (últimos 30/60/90 días)
- Comparativa periodo anterior
- Detección de anomalías

**FinOps:**
- Budget LLM mensual
- Consumo por capability (reasoning, synthesis, classification)
- Proyección fin de mes
- Hard stops activos

#### Cómo Usarlo

**Caso: Revisión semanal de negocio (Owner)**

1. Lunes a primera hora, abre `/command-center`
2. Revisa snapshot ejecutivo:
   - ¿Estamos generando suficientes leads?
   - ¿Cuántos sellers P5 tenemos activos?
   - ¿Cuántos mandatos firmamos esta semana?
   - ¿Cuál es el pipeline value total?
3. Compara con semana anterior
4. Identifica tendencias:
   - Si leads caen → priorizar prospección
   - Si sellers P5 están altos pero mandatos bajos → revisar copy de captación
   - Si matches altos pero cierres bajos → revisar proceso de follow-up
5. Toma decisiones estratégicas basadas en datos

### 5.6 Deal Margin Simulator

**Ruta:** `/deal-margin-simulator`
**Acceso:** Owner, Manager

#### Propósito

**Simulador de margen por operación** para calcular comisiones, costos y beneficio neto.

#### Funcionalidad Principal

**Inputs:**
- Precio de venta
- % comisión (default: 3%)
- Costos variables (marketing, staging, etc.)
- Costos fijos

**Outputs:**
- Comisión bruta
- Costos totales
- Margen neto
- % de margen

**Comparación de Escenarios:**
- Simula múltiples escenarios
- Compara side-by-side
- Identifica escenario óptimo

#### Cómo Usarlo

**Caso: Calcular margen de operación**

1. Entra a `/deal-margin-simulator`
2. Introduce:
   - Precio venta: €1,200,000
   - Comisión: 3% (€36,000)
   - Costos variables: €2,000 (fotografía profesional, staging virtual)
   - Costos fijos: €500 (administrativos)
3. Pulsa **Simulate**
4. Resultado:
   - Comisión bruta: €36,000
   - Costos totales: €2,500
   - Margen neto: €33,500
   - % margen: 92.9%

**Caso: Comparar escenarios**

1. Simula escenario base (comisión 3%)
2. Pulsa **Add Scenario**
3. Simula escenario alternativo (comisión 2.5%)
4. Compara resultados
5. Decide cuál negociar con el cliente

### 5.7 Source Observatory

**Ruta:** `/source-observatory`
**Acceso:** Owner, Manager

#### Propósito

**Observatorio de performance de fuentes de leads** para optimizar inversión en canales de adquisición.

#### Funcionalidad Principal

**Métricas por Fuente:**
- Fuente (web form, StateFox, referidos, etc.)
- Leads generados
- Tasa de conversión
- Costo por lead (CPL)
- Costo por adquisición (CPA)
- ROI

**Gráficos:**
- Distribución de leads por fuente
- Evolución temporal por fuente
- Comparativa de conversión

#### Cómo Usarlo

**Caso: Evaluar ROI de fuentes**

1. Entra a `/source-observatory`
2. Ordena fuentes por ROI descendente
3. Identifica:
   - Fuentes con ROI alto → escalar inversión
   - Fuentes con ROI bajo → optimizar o pausar
4. Analiza tasa de conversión:
   - Si conversión baja → revisar calidad de leads
   - Si conversión alta → priorizar seguimiento
5. Toma decisiones de inversión basadas en datos

---

## 6. Casos de Uso Prácticos

### 6.1 Por Rol: Owner

#### Caso 1: Revisión Semanal de Negocio

**Objetivo:** Evaluar salud comercial en 20 minutos y asignar prioridades al equipo.

**Pasos:**
1. Lunes 9:00h, abre **Command Center**
2. Revisa snapshot ejecutivo:
   - Leads: 25 esta semana (vs 30 semana anterior) ⚠️
   - Sellers P5: 8 activos (excelente) ✓
   - Mandatos firmados: 2 este mes (objetivo: 3) ⚠️
   - Matches activos: 45 (20 con score > 80) ✓
3. Abre **Dashboard** y revisa **AgentStream**:
   - prospection_weekly ejecutado OK ✓
   - recap_weekly ejecutado OK ✓
   - territorial_sync hace 5 días ⚠️ → programar refresh
4. Abre **Leads** y filtra por "Nuevo" sin atender:
   - 3 leads nuevos sin contactar > 24h ❌
   - Asigna a Manager para seguimiento urgente
5. Abre **Sellers** y filtra por P5 en "Detected":
   - 2 sellers P5 sin contactar
   - Asigna a ti mismo para contacto hoy
6. Crea tareas para equipo:
   - Manager: "Contactar 3 leads nuevos urgente"
   - Agent: "Follow-up 5 matches score > 85"
7. Ejecuta refresh territorial en `/intelligence`
8. Cierra semana con plan claro

**Resultado esperado:**
- Tablero limpio de tareas críticas
- Prioridades claras por miembro
- Pipeline con acciones concretas para generar cierres

#### Caso 2: Optimizar Inversión en Fuentes

**Objetivo:** Decidir dónde invertir presupuesto de marketing.

**Pasos:**
1. Abre **Source Observatory**
2. Revisa ROI por fuente (últimos 30 días):
   - Web form: 25 leads, conversión 20%, CPL €15, ROI 400% ✓
   - Facebook Ads: 40 leads, conversión 5%, CPL €30, ROI 50% ⚠️
   - StateFox: 15 sellers, conversión 40%, CPL €0, ROI ∞ ✓
   - Referidos: 5 leads, conversión 60%, CPL €0, ROI ∞ ✓
3. Decisiones:
   - **Escalar:** Web form (ROI alto), referidos (conversión alta)
   - **Optimizar:** Facebook Ads (conversión baja) → revisar targeting
   - **Mantener:** StateFox (fuente orgánica de alto valor)
4. Ajusta presupuesto:
   - Reduce Facebook Ads de €1200/mes a €600/mes
   - Aumenta inversión en SEO (web form) de €800 a €1400/mes
5. Comunica cambios al equipo

**Resultado esperado:**
- Budget optimizado según datos reales
- Mayor ROI global
- Reducción de CPL promedio

### 6.2 Por Rol: Manager

#### Caso 1: Gestión Diaria de Leads

**Objetivo:** Convertir leads en oportunidades activas en < 2h.

**Pasos:**
1. 9:00h, abre **Dashboard**
2. Revisa **LeadsPulse**:
   - 3 leads nuevos detectados
   - Lead 1: P4, presupuesto €900k, zona Andratx ⭐
   - Lead 2: P3, presupuesto €500k, zona Calvià
   - Lead 3: P2, presupuesto €300k, zona Son Ferrer
3. Prioriza Lead 1 (P4):
   - Abre detalle
   - Lee notas: "Busca villa con vistas, máximo 3 meses"
   - Verifica email y teléfono disponibles
4. Llama inmediatamente:
   - Presenta Anclora y eXp
   - Confirma presupuesto y criterios
   - Agenda visita para mañana
5. Registra interacción:
   - Canal: phone
   - Resultado: interesado, visita agendada
   - Notas: "Prefiere vistas mar, flexible en m²"
6. Actualiza estado a "Cualificado"
7. Vincula con 3 propiedades de portfolio que encajan
8. Crea tarea: "Enviar dossier 3 villas a Lead 1 hoy 14:00h"
9. Repite con Lead 2 y 3 (emails si no contestan teléfono)

**Resultado esperado:**
- Leads atendidos < 2h desde entrada
- Aumento de ratio de contacto efectivo
- Pipeline lleno de oportunidades activas

#### Caso 2: Desbloquear Pipeline de Propiedades

**Objetivo:** Mover propiedades estancadas en "Valoración".

**Pasos:**
1. Abre **Dashboard** y revisa **PropertyPipeline**
2. Detecta: 8 propiedades en "Valoración" (cuello de botella)
3. Abre **Properties** y filtra por estado "Valoración"
4. Para cada propiedad:
   - Verifica datos completos (dirección, m², fotos)
   - Si faltan datos → contacta propietario para completar
   - Si datos completos → ejecuta CMA:
     - Usa **RadarTerritorial** para contexto de zona
     - Compara con propiedades similares
     - Calcula precio recomendado
   - Registra CMA en notas de propiedad
   - Cambia estado a "Listada"
5. Para propiedades listadas, publica en portales:
   - Abre **Feed Orchestrator**
   - Selecciona Idealista
   - Valida cada propiedad
   - Pulsa **Publish**
6. Crea tareas de seguimiento:
   - "Monitorear visitas Idealista - Villa Andratx" (en 3 días)

**Resultado esperado:**
- Pipeline desbloqueado
- 8 propiedades publicadas activamente
- Mayor visibilidad en portales

### 6.3 Por Rol: Agent

#### Caso 1: Ejecución de Tareas del Día

**Objetivo:** Completar tareas asignadas sin acumular backlog.

**Pasos:**
1. 9:00h, abre **Dashboard**
2. Revisa **TasksToday**:
   - 5 tareas pendientes
   - 2 vencidas (ayer) ❌
   - 3 de hoy
3. Ordena mentalmente por impacto comercial:
   - Tarea 1 (vencida): "Llamar Ana García - seguimiento propuesta" → URGENTE
   - Tarea 2 (hoy): "Enviar dossier villas a Lead X" → ALTA
   - Tarea 3 (hoy): "Actualizar fotos propiedad Y" → MEDIA
   - Tarea 4 (hoy): "Revisar CMA zona Z" → BAJA
   - Tarea 5 (vencida): "Organizar archivos" → BAJA
4. Ejecuta Tarea 1:
   - Llama a Ana García
   - Resultado: "Interesada pero necesita consultar con marido"
   - Registra resultado en notas
   - Reprograma seguimiento para dentro de 2 días
   - Marca como completada (con reprogramación)
5. Ejecuta Tarea 2:
   - Abre lead X
   - Selecciona 3 villas del portfolio
   - Envía dossier por email
   - Registra acción
   - Marca como completada
6. Ejecuta Tarea 3:
   - Abre propiedad Y en `/properties`
   - Sube nuevas fotos (7 fotos HD)
   - Actualiza descripción
   - Guarda cambios
   - Marca tarea como completada
7. Tareas 4 y 5 (no críticas):
   - Reprograma para mañana
   - Añade nota: "Priorizado tareas comerciales"

**Resultado esperado:**
- Cero tareas críticas vencidas
- Follow-ups comerciales ejecutados
- Backlog gestionado con criterio

#### Caso 2: Follow-up de Match Activo

**Objetivo:** Avanzar match por pipeline hasta visita.

**Pasos:**
1. Abre **Prospection operativa**
2. Filtra por "Contacted" (matches ya contactados)
3. Localiza match "Ana García - Villa Andratx" (score 88)
4. Abre detalle del match
5. Revisa última interacción:
   - Fecha: hace 3 días
   - Canal: email
   - Resultado: "Interesada, quiere saber más"
6. Acción de seguimiento:
   - Llama a Ana
   - Presenta villa en detalle
   - Responde preguntas
   - Propone visita para este viernes
7. Ana acepta visita:
   - Registra actividad: "Visita programada viernes 14:00h"
   - Cambia estado match a "Viewing"
   - Crea tarea: "Preparar villa para visita viernes"
   - Crea tarea: "Llamar Ana viernes 13:00h para confirmar"

**Resultado esperado:**
- Match avanzado en pipeline
- Visita programada
- Mayor probabilidad de cierre

---

## 7. Troubleshooting

### 7.1 Errores Comunes

#### Error: "Email o contraseña incorrectos"

**Causa:** Credenciales inválidas o usuario no existe.

**Solución:**
1. Verifica que el email sea correcto (sin espacios, minúsculas)
2. Verifica que la contraseña sea correcta
3. Si olvidaste la contraseña:
   - Pulsa "Olvidé mi contraseña"
   - Introduce email
   - Revisa tu bandeja (y spam)
   - Sigue el enlace de recuperación
4. Si persiste:
   - Verifica que tu cuenta esté creada
   - Contacta al Owner para verificar tu membresía

---

#### Error: "Acceso restringido" en módulo Team

**Causa:** Tu rol no tiene permisos para gestionar equipo.

**Solución:**
1. Verifica tu rol en **Profile**
2. Solo Owner tiene acceso completo a `/team`
3. Si eres Manager o Agent, no puedes:
   - Invitar miembros
   - Cambiar roles
   - Suspender cuentas
4. Si necesitas estos permisos:
   - Contacta al Owner
   - Solicita promoción a Owner (si aplica)
   - El Owner puede ajustar tu rol desde `/team`

---

#### Error: "Cuenta inactiva"

**Causa:** Tu membresía no está activa en la organización.

**Solución:**
1. Tu estado puede ser:
   - **Pending:** Invitación no aceptada → acepta invitación
   - **Suspended:** Cuenta bloqueada temporalmente → contacta Owner
   - **Removed:** Fuera de organización → solicita nueva invitación
2. Contacta al Owner:
   - Proporciona tu email
   - Solicita reactivación
3. El Owner puede:
   - Reactivar cuenta desde `/team`
   - Reenviar invitación
   - Crear nueva membresía

---

#### Error: "No invitado / Invitación requerida"

**Causa:** Intentas crear cuenta sin invitación válida.

**Solución:**
1. Anclora Nexus es invite-only
2. No puedes crear cuenta sin invitación previa
3. Solicita invitación al Owner:
   - Proporciona tu email
   - Especifica tu rol esperado (Agent, Manager)
4. El Owner te enviará invitación desde `/team`
5. Recibirás email con enlace
6. Sigue el enlace para completar registro

---

#### Error: Login correcto pero no entra al dashboard

**Causa:** Autenticación exitosa pero membresía no activa o no existe.

**Solución:**
1. Verifica que tu membresía esté activa:
   - Pide al Owner que revise tu estado en `/team`
   - Debe estar en estado "Active"
2. Recarga la página (Ctrl+F5 o Cmd+Shift+R)
3. Limpia caché del navegador
4. Intenta en modo incógnito
5. Si persiste:
   - Cierra sesión completamente
   - Vuelve a iniciar sesión
6. Si aún no funciona:
   - Contacta al Tech Lead
   - Proporciona: email, rol esperado, timestamp del intento

---

#### Error: Widget no carga datos (spinner infinito)

**Causa:** Error en backend, timeout o permisos insuficientes.

**Solución:**
1. Recarga la página (F5)
2. Verifica tu conexión a internet
3. Abre consola del navegador (F12):
   - Ve a pestaña "Console"
   - Busca errores en rojo
   - Copia el mensaje de error
4. Si ves error 403 (Forbidden):
   - Tu rol no tiene acceso a esos datos
   - Verifica permisos con Owner
5. Si ves error 500 (Server Error):
   - Error en backend
   - Reporta al Tech Lead con:
     - Widget afectado
     - Hora exacta
     - Mensaje de error (screenshot)

---

#### Error: "Budget limit exceeded"

**Causa:** Has alcanzado el hard stop de presupuesto LLM mensual.

**Solución:**
1. Este es un hard stop constitucional
2. El sistema bloquea automáticamente ejecuciones de agentes
3. Opciones:
   - **Espera a próximo mes:** El límite se resetea el día 1
   - **Solicita ajuste de budget:**
     - Contacta al Owner
     - Justifica necesidad de aumento
     - Owner puede ajustar desde `/command-center` → FinOps
4. Mientras tanto:
   - Puedes usar funcionalidad manual (sin agentes IA)
   - Prioriza tareas críticas
   - Reduce ejecuciones no esenciales

---

#### Error: No puedo subir fotos a propiedad

**Causa:** Archivo demasiado grande, formato no soportado o permisos de storage.

**Solución:**
1. Verifica formato:
   - Soportado: JPG, PNG, WebP
   - No soportado: TIFF, BMP, RAW
2. Verifica tamaño:
   - Máximo por foto: 10MB
   - Si es mayor, comprime la imagen:
     - Usa herramientas como TinyPNG
     - Reduce resolución a 1920x1080 máximo
3. Verifica permisos:
   - Roles Agent y Manager pueden subir fotos
   - Si eres Agent, verifica que no haya política restrictiva
4. Si persiste:
   - Intenta subir una foto a la vez
   - Recarga la página y reintenta
   - Contacta al Tech Lead si falla sistemáticamente

---

### 7.2 FAQ

#### ¿Puedo usar Anclora Nexus desde móvil?

**Respuesta:** Sí, la interfaz es responsive y funciona en navegadores móviles.

**Recomendación:**
- Para mejor experiencia, usa tablet (10"+) o desktop
- En móvil (< 7"), algunos widgets pueden ser difíciles de usar
- Funciones críticas (leads, tareas) están optimizadas para móvil

---

#### ¿Cómo cambio el idioma de la interfaz?

**Respuesta:**
1. Usa el selector de idioma (🌐) en el header superior derecho
2. Idiomas soportados:
   - ES (Español) - Default
   - EN (English)
   - DE (Deutsch)
   - RU (Русский)
3. El cambio es instantáneo (no requiere recargar)
4. Tu preferencia se guarda en localStorage

---

#### ¿Qué significa cada estado de lead?

**Estados disponibles:**

| Estado | Significado | Siguiente acción típica |
|--------|-------------|-------------------------|
| **Nuevo** | Lead recién ingresado, sin contactar | Contactar < 24h |
| **Contactado** | Primera interacción realizada | Cualificar y validar presupuesto |
| **Cualificado** | Lead con potencial confirmado | Enviar propuestas |
| **Propuesta** | Oferta comercial enviada | Hacer seguimiento, agendar visita |
| **Ganado** | Lead convertido en cliente | Cerrar operación |
| **Perdido** | Lead descartado | Registrar motivo, archivar |

---

#### ¿Puedo exportar datos de la aplicación?

**Respuesta:** Sí, la mayoría de tablas tienen opción de exportación.

**Cómo exportar:**
1. Ve al módulo (Leads, Properties, Tasks)
2. Aplica filtros si quieres exportar solo un subset
3. Busca botón "Exportar" (icono 📥)
4. Selecciona formato:
   - CSV (para Excel, Google Sheets)
   - JSON (para procesamiento)
5. El archivo se descarga automáticamente

**Permisos:**
- Owner y Manager: pueden exportar todo
- Agent: puede exportar solo leads/tareas asignadas

**Nota:** Datos sensibles (contraseñas, API keys) no se incluyen en exports.

---

#### ¿Con qué frecuencia se actualiza el RadarTerritorial?

**Respuesta:** Depende del sync pack NotebookLM.

**Frecuencia estándar:**
- Sync programado: **Cada domingo 18:00h** (cron automático)
- Sync manual: Puedes ejecutarlo on-demand desde `/intelligence`

**Cómo verificar última actualización:**
1. Abre `/intelligence`
2. Ve card "Territorial Sync Status"
3. Verifica timestamp de última ejecución

**Si está desactualizado (> 7 días):**
1. Ejecuta refresh manual:
   - Botón "Refresh Territorial Sync"
   - Tiempo estimado: 2-5 minutos
2. Si falla:
   - Revisa `/automation-alerting` para alertas
   - Contacta al Tech Lead

---

#### ¿Cómo sé si un seller es P5 (Whale)?

**Respuesta:** El sistema calcula prioridad automáticamente con scoring IA.

**Fórmula (simplificada):**
- **35%** Valor de propiedad (precio absoluto y €/m²)
- **25%** Urgencia de venta (días en mercado, señales de motivación)
- **25%** Encaje con zona target (Andratx, Calvià premium)
- **15%** Calidad de fuente (StateFox > FSBO > manual)

**Umbrales:**
- **P5 (Whale):** Score 80-100 → Mandato casi seguro
- **P4:** Score 60-79 → Alto potencial
- **P3:** Score 40-59 → Potencial medio
- **P2:** Score 20-39 → Potencial bajo
- **P1:** Score 0-19 → Frío

**Indicadores visuales:**
- Badge dorado con "P5" en tabla de sellers
- Notificación automática cuando se detecta nuevo P5
- Aparece primero en ordenación por defecto

---

#### ¿Qué hago si detecto un error en la aplicación?

**Respuesta:** Reporta el error con el máximo detalle posible.

**Información a incluir:**
1. **Email afectado:** Tu usuario
2. **Módulo y acción exacta:** Ej: "/leads, al intentar cambiar estado de lead"
3. **Mensaje de error:** Screenshot o texto completo
4. **Hora aproximada:** Ej: "Hoy 10:30h"
5. **Navegador y sistema:** Ej: "Chrome 120 en Windows 11"
6. **Pasos para reproducir:** Qué hiciste antes del error

**Canal de reporte:**
- Crea tarea en `/tasks` con título "BUG: [descripción corta]"
- Asigna a Owner
- Owner escalará al Tech Lead si es necesario

**Criticidad:**
- **Bloqueante:** No puedes trabajar → Reporta inmediatamente (llamada/WA)
- **Alta:** Afecta funcionalidad clave → Reporta hoy
- **Media:** Afecta funcionalidad secundaria → Reporta esta semana
- **Baja:** Cosmético o typo → Reporta cuando tengas tiempo

---

#### ¿Puedo usar Anclora Nexus offline?

**Respuesta:** No, Anclora Nexus requiere conexión a internet activa.

**Motivo:**
- Datos obtenidos desde Neon
- Ejecución de agentes IA requiere conectividad
- Sync territorial consume APIs externas

**Recomendación:**
- Asegura conexión estable antes de trabajar
- Si pierdes conexión, guarda cambios locales cuando vuelva
- Algunos navegadores cachean la UI, pero funcionalidad requiere internet

---

## 8. Anexos

### 8.1 Matriz de Permisos por Rol

| Módulo / Acción | Owner | Manager | Agent |
|------------------|-------|---------|-------|
| **Dashboard** (ver) | ✅ | ✅ | ✅ |
| **Leads** (ver todos) | ✅ | ✅ | ❌ (solo asignados) |
| **Leads** (crear/editar) | ✅ | ✅ | ✅ |
| **Properties** (ver) | ✅ | ✅ | ✅ (read-only) |
| **Properties** (crear/editar) | ✅ | ✅ | ❌ |
| **Tasks** (ver todas) | ✅ | ✅ | ❌ (solo asignadas) |
| **Tasks** (crear/asignar) | ✅ | ✅ | ✅ (solo a sí mismo) |
| **Team** (ver) | ✅ | ✅ (read-only) | ❌ |
| **Team** (gestionar) | ✅ | ❌ | ❌ |
| **Prospection** (ver) | ✅ | ✅ | ✅ |
| **Sellers** (ver) | ✅ | ✅ | ✅ |
| **Sellers** (contactar) | ✅ | ✅ | ✅ |
| **Intelligence** (ver) | ✅ | ✅ | ❌ |
| **Ingestion** (ver) | ✅ | ✅ | ❌ |
| **Data Quality** (resolver) | ✅ | ✅ | ❌ |
| **Feed Orchestrator** (publicar) | ✅ | ✅ | ❌ |
| **Automation** (gestionar) | ✅ | ❌ | ❌ |
| **Command Center** (ver) | ✅ | ❌ | ❌ |

### 8.2 Glosario de Términos

| Término | Definición |
|---------|------------|
| **CMA** | Comparative Market Analysis - Análisis de mercado comparativo |
| **FSBO** | For Sale By Owner - Propiedad en venta sin agente |
| **HITL** | Human-In-The-Loop - Revisión humana obligatoria |
| **ICP** | Ideal Client Profile - Perfil de cliente ideal |
| **NotebookLM** | Herramienta de Google para RAG (Retrieval-Augmented Generation) |
| **P5 (Whale)** | Seller de prioridad máxima (score 80-100) |
| **RLS** | Row-Level Security - Seguridad a nivel de fila en base de datos |
| **StateFox** | Canal Telegram para detección de oportunidades seller-side |
| **Sync Pack** | Paquete de documentos sincronizados con NotebookLM |

### 8.3 Atajos de Teclado

| Atajo | Acción |
|-------|--------|
| `Ctrl + K` (o `Cmd + K`) | Abrir búsqueda global |
| `Ctrl + /` | Abrir paleta de comandos |
| `Escape` | Cerrar modal/drawer |
| `Ctrl + S` | Guardar cambios (en formularios) |
| `Ctrl + Enter` | Enviar formulario |

---

## 9. Información de Contacto y Soporte

**Organización:** Anclora Private Estates by eXp Realty Spain

**Owner:** Toni Amengual
- Email: toni@anclora.com
- Teléfono: [Confidencial]

**Soporte Técnico:**
- Email: tech@anclora.com
- Horario: Lunes a Viernes, 9:00h - 18:00h CET

**Reportar Bugs:**
- Crear tarea en `/tasks` con prefijo "BUG:"
- Para issues críticos: contacto directo con Owner

---

## 10. Historial de Versiones del Manual

| Versión | Fecha | Cambios |
|---------|-------|---------|
| 1.2.3 | 2026-03-10 | Manual completo generado automáticamente con ANCLORA-UMG-001 |
| 1.2.2 | 2026-03-05 | Versión manual previa (parcial) |

---

**Fin del Manual de Usuario - Anclora Nexus v1.2.3**

🤖 Generado con [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>

---

© 2026 Anclora Private Estates. Todos los derechos reservados.
"""

    return manual_content

def main():
    print("=" * 60)
    print("🚀 GENERADOR DE MANUAL DE USUARIO - ANCLORA NEXUS")
    print("=" * 60)
    print()

    # Step 1: Generate Markdown
    print("📝 Paso 1/2: Generando versión Markdown...")
    manual = generate_manual()

    output_dir = Path("/home/dev/proyectos/anclora-nexus/public/docs/manual-usuario")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path_md = output_dir / "MANUAL_USUARIO_ANCLORA_NEXUS.md"

    with open(output_path_md, "w", encoding="utf-8") as f:
        f.write(manual)

    print(f"   ✅ Markdown generado: {output_path_md}")
    print(f"   Tamaño: {len(manual):,} caracteres")
    print()

    # Step 2: Convert to DOCX
    print("📄 Paso 2/2: Convirtiendo a formato DOCX...")

    script_dir = Path(__file__).parent
    convert_script = script_dir / "convert-manual-to-docx.py"

    if convert_script.exists():
        try:
            result = subprocess.run(
                ["python3", str(convert_script)],
                capture_output=True,
                text=True,
                check=True
            )
            print(result.stdout)
        except subprocess.CalledProcessError as e:
            print(f"   ⚠️  Error al convertir a DOCX:")
            print(f"   {e.stderr}")
            print(f"\n   💡 Puedes ejecutar manualmente:")
            print(f"   python3 scripts/convert-manual-to-docx.py")
    else:
        print(f"   ⚠️  Script de conversión no encontrado: {convert_script}")
        print(f"   💡 Ejecuta manualmente:")
        print(f"   python3 scripts/convert-manual-to-docx.py")

    print()
    print("=" * 60)
    print("✨ GENERACIÓN COMPLETADA")
    print("=" * 60)
    print()
    print("📁 Archivos generados:")
    print(f"   • Markdown: {output_path_md}")

    output_path_docx = output_dir / "MANUAL_USUARIO_ANCLORA_NEXUS.docx"
    if output_path_docx.exists():
        size_kb = output_path_docx.stat().st_size / 1024
        print(f"   • DOCX: {output_path_docx} ({size_kb:.1f} KB)")
    print()

if __name__ == "__main__":
    main()
