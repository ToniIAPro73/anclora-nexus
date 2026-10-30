# Anclora Internal App Contract

## Objetivo
Unificar la UX/UI de las aplicaciones internas sin borrar la identidad de cada producto. La lógica de interacción debe sentirse igual; la identidad puede variar en acento, tipografía secundaria y tono editorial.

Ámbito:
- `anclora-advisor-ai`
- `anclora-filestudio`
- `anclora-nexus`
- `anclora-content-generator-ai`
- `anclora-command-center`

Nota:
- `anclora-group` no forma parte de este contrato. Se gobierna como `Entidad Matriz` con branding propio.

## Piezas canónicas del design system

Toda aplicación interna debe componer su UI desde capas reales de `anclora-design-system`:

- `tokens` y `themes` para tema, contraste, foreground y estados
- `foundations` para tipografía, spacing, radius, border y elevation
- `components` para:
  - button
  - input
  - select
  - textarea
  - dialog
  - card
  - badge
  - tabs
- `patterns` para:
  - shell autenticado
  - toolbar de filtros
  - tablas/listas operativas
  - formularios densos
  - colas y paneles laterales

Regla:
- si una surface interna no existe aún en `anclora-design-system`, primero se promueve allí como pieza compartida o pattern, y después se consume en la app.

## Invariantes de grupo

### 1. Shell
- La pantalla debe seguir la jerarquía `header operativo + navegación persistente + área principal`.
- Las preferencias de usuario deben vivir en el mismo cuadrante del shell: cuenta, idioma, tema y logout.
- El estado activo de navegación debe ser inequívoco.
- No se permite cambiar el patrón de navegación entre vistas equivalentes sin razón funcional documentada.

### 2. Botones
- Familias obligatorias:
  - `primary`
  - `secondary`
  - `ghost`
  - `destructive`
- La acción principal debe ser la más visible de la vista.
- La acción destructiva no puede competir visualmente con la primaria.
- Los botones equivalentes deben compartir:
  - altura
  - radio
  - nivel de contraste
  - criterio de foreground por familia
  - transición de hover/focus
  - estado disabled
- Si la app soporta más de un tema, una misma familia de botón no puede cambiar arbitrariamente el color del texto o la legibilidad entre `dark` y `light`.

### 3. Cards y surfaces
- Toda card interactiva debe tener hover y focus consistentes.
- Las cards del mismo bloque deben moverse y elevarse con la misma intensidad.
- KPIs, quick actions y bloques de resumen deben seguir la misma gramática de superficie.
- Ninguna surface puede dejar texto técnico, IDs o labels largos saliéndose del contenedor.

### 4. Modales
- Se aplica `MODAL_CONTRACT.md`.
- Reglas adicionales del grupo:
  - formularios complejos: modal ancho o casi fullscreen antes que columna larga con scroll
  - selectores densos: paginación, tabs o segmentación antes que lista infinita
  - cierre superior derecho siempre visible
  - acciones primarias/secundarias siempre legibles en el footer

### 5. Formularios
- Label visible siempre.
- Placeholder sólo como ayuda.
- Errores y ayudas debajo del campo.
- Inputs, selects y textareas deben compartir altura y radio por familia.
- El autofill del navegador no puede romper dark mode ni contraste.

### 6. Listas, tablas y colas
- Toda lista operativa debe exponer estado, prioridad o contexto y una acción clara.
- Filtros y búsqueda en la parte superior inmediata del bloque.
- La lectura debe separar con claridad información, acción y destrucción.

### 7. Motion
- Se aplica `UI_MOTION_CONTRACT.md`.
- El motion interno debe ser corto, funcional y no teatral.
- No usar animaciones largas, rebotes ni desplazamientos que resten velocidad de lectura.

### 8. Localización
- Se aplica `LOCALIZATION_CONTRACT.md`.
- No se permite mezclar idiomas en una misma vista.
- Los layouts deben absorber expansiones de texto sin truncado agresivo.

### 9. Tema
- Los tokens base deben existir aunque una app publique un solo tema.
- No se permiten colores hardcodeados por pantalla si la semántica ya existe en el sistema UI.
- Los componentes nuevos deben nacer listos para tema real y para un futuro modo alternativo cuando el roadmap lo exija.
- Si una app usa `dark/light/system`, las familias semánticas de botones y controles deben conservar una lógica estable de foreground, contraste y prioridad entre temas.

## Reglas particulares por aplicación

### `anclora-advisor-ai`
- Baseline interna para:
  - preferencias persistidas
  - `dark/light/system`
  - bilingüe `es/en`
- Las futuras apps internas deben reutilizar este patrón de preferencias cuando no exista una razón fuerte para desviarse.

### `anclora-filestudio`
- Servicio interno transversal de conversión y procesamiento documental.
- Debe priorizar privacidad por defecto, clasificación de sensibilidad, retención limitada, scopes claros y trazabilidad de jobs.
- La integración confirmada pasa por `anclora-nexus`, que conserva identidad, consentimiento, routing y estado visible para usuario.

### `anclora-nexus`
- Mantener dark como contrato operativo principal.
- Mantener cobertura `es/en/de/ru`.
- Los contratos existentes de `surface` y `page primitives` siguen vigentes y deben leerse como implementación concreta del grupo interno.
- No introducir nuevos portales, cards o modales fuera de la gramática ya definida en `sdd/contracts`.

### `anclora-content-generator-ai`
- Contrato objetivo:
  - `es/en`
  - toggle visible de idioma
  - `dark/light/system`
- El tema ya está maduro; la deuda principal es cerrar i18n visible y completa.

## Gate de aceptación

Una feature interna no está lista si:
- introduce un quinto estilo de botón sin contrato
- rompe la jerarquía de shell o preferencias
- añade un modal denso con scroll evitable
- deja textos visibles fuera de i18n cuando la app requiere localización
- usa un hover o elevación arbitraria que rompa el bloque
- cambia el foreground o la legibilidad de una familia de botón entre temas sin documentarlo como variante real
- resuelve un botón, modal, tabla o shell con una implementación local cuando ya existe una pieza canónica en `anclora-design-system`
