# Plan: Integración de tdd-implement y coding-guidelines en SDD

## Objetivo

Que cada fase SDD tenga una referencia explícita a las skills que debe cargar, indicando rol (ARCHITECT/DEVELOPER/REVIEWER) y quéaspectos de la skill aplican.

---

## Análisis Gaps por Fase

### sdd-apply ✅ — YA CORRECTO
- **tdd-implement**: EXPLÍCITO — línea 71 menciona `read-task-spec`, `tdd-implement`, `coding-guidelines`
- **coding-guidelines**: EXPLÍCITO — mismo bloque
- **Estado**: Cumplido. Solo verificar que la versión "model-small" también los tenga.

### sdd-verify ✅ — YA CORRECTO
- **tdd-implement**: EXPLÍCITO — línea 67 menciona `read-task-spec`, `tdd-implement`, `coding-guidelines`
- **coding-guidelines**: EXPLÍCITO — mismo bloque
- **Estado**: Cumplido.

### sdd-design ❌ — GAPS
- **Problema**: Solo dice "follow Section A" (genérico). No dice qué skills cargar.
- **Rol correcto**: ARCHITECT (diseño de boundaries) + DEVELOPER (implementación函数)
- **coding-guidelines aplica en**:
  - `deep-modules.md` — evaluar si cada decisión de diseño forma un deep module
  - `information-hiding.md` — qué conocimiento esconder detrás de cada interface
  - `general-purpose.md` — qué tan general debe ser cada interface diseñada
  - `layers.md` — si cada capa aporta una nueva abstracción
  - `classes.md` — together or apart por conocimiento
- **tdd-implement**: NO aplica en diseño (es para implementación)

### sdd-spec ❌ — GAPS
- **Problema**: Solo dice "follow Section A" (genérico). No menciona skills.
- **Rol correcto**: ARCHITECT (diseño de requirements y boundaries)
- **coding-guidelines aplica en**:
  - `information-hiding.md` — qué knowledge vive detrás de cada requirement
  - `deep-modules.md` — cada requirement ¿es un deep module o un requirement trivial?
  - `general-purpose.md` — qué tan general debe ser cada capability
- **tdd-implement**: NO aplica en specs (es para implementación)

### sdd-propose ❌ — GAPS
- **Problema**: No menciona skills.
- **Rol correcto**: ARCHITECT (diseño de scope y capabilities antes de código)
- **coding-guidelines aplica en**:
  - `deep-modules.md` — evaluar si el cambio propuesto mejora o empeora la profundidad del sistema
  - `information-hiding.md` — qué secretos esconde el cambio, cuáles expone
  - `layers.md` — el cambio introduce capas passthrough o contribuye con nueva abstracción
- **tdd-implement**: NO aplica en proposal

### sdd-tasks ❌ — GAPS
- **Problema**: No menciona skills.
- **Rol correcto**: ARCHITECT (estimación de workload, decisión de single-PR y size-exception) + DEVELOPER (estructura de tareas)
- **coding-guidelines aplica en**:
  - `functions.md` — cada tarea ¿es una función independently understandable?
  - `deep-modules.md` — las tareas agrupan por depth o solo por líneas de código
  - `information-hiding.md` — cada tarea escond knowledge o lo expone
- **tdd-implement**: NO aplica en tasks

### sdd-explore ❌ — GAPS
- **Problema**: No menciona skills.
- **Rol correcto**: ARCHITECT (investigar codebase, evaluar patrones existentes)
- **coding-guidelines aplica en**:
  - `deep-modules.md` — evaluar depth de módulos existentes
  - `information-hiding.md` — qué knowledge está leakado en el código explorado
  - `functions.md` — identificar funciones coupled o conjoined
  - `layers.md` — identificar pass-through layers
- **tdd-implement**: NO aplica en explore

### sdd-init ❌ — NO RELEVANTE
- Detecta stack y tooling. No produce código. Skills no aplican.

### sdd-archive ❌ — NO RELEVANTE
- Mergea specs y mueve archivos. Skills no aplican directamente.

---

## Acciones Requeridas

### 1. sdd-design.md
**Cambio**: Agregar bloque `## Skills to load before work` explícito.

```
## Skills to load before work

Load these skills before any other work:
- `skills/coding-guidelines/SKILL.md` — role: ARCHITECT + DEVELOPER

When loading coding-guidelines:
- Read `references/deep-modules.md` first (mandatory for every boundary)
- Read `references/information-hiding.md` (interface design)
- Read `references/layers.md` (system structure)
- Read `references/classes.md` (class boundaries)
- Read `references/general-purpose.md` (interface generality)
- Hold question: "Where does each piece of knowledge live, and does every boundary I draw hide something real?"
```

**Por qué**: El diseño es la fase donde más se necesita Ousterhout — definir boundaries, decidir qué esconder, evaluar profundidad.

### 2. sdd-spec.md
**Cambio**: Agregar bloque `## Skills to load before work`.

```
## Skills to load before work

Load these skills before any other work:
- `skills/coding-guidelines/SKILL.md` — role: ARCHITECT

When loading coding-guidelines:
- Read `references/information-hiding.md` first (requirements as contracts)
- Read `references/deep-modules.md` (each requirement = a module boundary)
- Read `references/general-purpose.md` (capability generality)
- Hold question: "Is this knowledge the caller NEEDS, or a leaked decision?"
```

**Por qué**: Specs definen requirements que se convierten en módulos. La skill ayuda a decidir boundaries de capabilities.

### 3. sdd-propose.md
**Cambio**: Agregar bloque `## Skills to load before work`.

```
## Skills to load before work

Load these skills before any other work:
- `skills/coding-guidelines/SKILL.md` — role: ARCHITECT

When loading coding-guidelines:
- Read `references/deep-modules.md` first (change amplification check)
- Read `references/information-hiding.md` (what secrets does this change expose/hide)
- Read `references/layers.md` (does this introduce pass-through layers)
- Hold question: "Does this change make the system easier or harder to understand?"
```

**Por qué**: El proposal define scope y approach. Evaluar si la propuesta mejora o empeora la complejidad.

### 4. sdd-tasks.md
**Cambio**: Agregar bloque `## Skills to load before work`.

```
## Skills to load before work

Load these skills before any other work:
- `skills/coding-guidelines/SKILL.md` — role: ARCHITECT + DEVELOPER

When loading coding-guidelines:
- Read `references/functions.md` first (independence test per task)
- Read `references/deep-modules.md` (depth vs line count)
- Read `references/information-hiding.md` (task boundaries — what to hide)
- Hold question: "Can each task be understood on its own?"
```

**Por qué**: Tasks deben ser independently actionable. La skill ayuda a no crear tareas vagas o acopladas.

### 5. sdd-explore.md
**Cambio**: Agregar bloque `## Skills to load before work`.

```
## Skills to load before work

Load these skills before any other work:
- `skills/coding-guidelines/SKILL.md` — role: ARCHITECT

When loading coding-guidelines:
- Read `references/deep-modules.md` first (evaluate module depth)
- Read `references/information-hiding.md` (identify leaked knowledge)
- Read `references/functions.md` (identify conjoined functions)
- Read `references/layers.md` (identify pass-through layers)
- Hold question: "What complexity symptoms exist in the codebase?"
```

**Por qué**: Explore evalúa el estado actual del codebase. La skill ayuda a identificar smells.

### 6. sdd-apply.md (model-small)
**Verificación**: La versión "model-small" (líneas 252-306) dice en paso 1: "Load the SKILL.md paths passed by the orchestrator (expected: read-task-spec, tdd-implement, coding-guidelines)". Ya está correcto.

### 7. sdd-verify.md (model-small)
**Verificación**: La versión "model-small" (líneas 95-141) no menciona skills explícitamente. Agregar:

```
## Skills to load before work

Load these skills before any other work:
- `skills/tdd-implement/SKILL.md` — para auditing de TDD evidence
- `skills/coding-guidelines/SKILL.md` — role: REVIEWER

When loading coding-guidelines:
- Read `references/deep-modules.md` first (evaluar si implementación hace deep modules)
- Hold question: "Which red flag is this diff about to introduce?"
```

---

## Archivo de Referencia Creado

Crear `prompts/sdd/references/skill-routing.md` como referencia central:

```markdown
# SDD Phase → Skill Routing

## Tabla de Referencia

| Phase | tdd-implement | coding-guidelines (role) |
|-------|:---:|:---:|
| sdd-init | ❌ | ❌ |
| sdd-explore | ❌ | ARCHITECT |
| sdd-propose | ❌ | ARCHITECT |
| sdd-spec | ❌ | ARCHITECT |
| sdd-design | ❌ | ARCHITECT + DEVELOPER |
| sdd-tasks | ❌ | ARCHITECT + DEVELOPER |
| sdd-apply | ✅ MANDATORY | DEVELOPER |
| sdd-verify | ✅ (audit) | REVIEWER |
| sdd-archive | ❌ | ❌ |
| sdd-onboard | ✅ (ejemplo) | Todas (ejemplo) |

## coding-guidelines: Qué leer por rol

### ARCHITECT (fases: explore, propose, spec, design)
Orden de lectura:
1. `deep-modules.md` — mandatory, el yardstick para cada boundary
2. `information-hiding.md` — secrets y decisiones
3. `layers.md` — estructura de capas
4. `classes.md` — together or apart por conocimiento
5. `general-purpose.md` — generalidad de interfaces

### DEVELOPER (fases: design, tasks, apply)
Orden de lectura:
1. `functions.md` — independence test
2. `classes.md` — same independence test at class scope
3. `information-hiding.md` — no leak data structures
4. `deep-modules.md` — depth yardstick
5. `layers.md` —拒绝 pass-through

### REVIEWER (fase: verify)
Orden de lectura:
1. Red-flag index (SKILL.md lines 429-451)
2. `information-hiding.md` — duplicated decisions
3. `deep-modules.md` — shallow modules
4. `functions.md` — conjoined functions
5. `layers.md` — pass-through methods/variables

## tdd-implement: Cuándo aplica

- **sdd-apply**: SIEMPRE — es el método de implementación
- **sdd-verify**: Para auditar TDD evidence del apply
- **sdd-onboard**: Como ejemplo narrado
- **Todas las demás**: NO aplica
```

---

## Resumen de Cambios

| Archivo | Cambio | Prioridad |
|---------|--------|----------|
| `prompts/sdd/sdd-design.md` | Agregar Skills block + coding-guidelines ARCHITECT+DEVELOPER | ALTA |
| `prompts/sdd/sdd-spec.md` | Agregar Skills block + coding-guidelines ARCHITECT | ALTA |
| `prompts/sdd/sdd-propose.md` | Agregar Skills block + coding-guidelines ARCHITECT | ALTA |
| `prompts/sdd/sdd-tasks.md` | Agregar Skills block + coding-guidelines ARCHITECT+DEVELOPER | ALTA |
| `prompts/sdd/sdd-explore.md` | Agregar Skills block + coding-guidelines ARCHITECT | MEDIA |
| `prompts/sdd/sdd-verify.md` (model-small) | Agregar Skills block + roles | MEDIA |
| `prompts/sdd/references/skill-routing.md` | Crear archivo de referencia central | ALTA |

---

## Criterio de Éxito

Un LLM que ejecute cualquier fase SDD sabe:
1. Qué skills cargar (explícitamente, no por "match triggers")
2. Qué rol cumplir (ARCHITECT/DEVELOPER/REVIEWER)
3. Qué archivos de referencia leer de cada skill
4. Qué pregunta mantener en mente mientras trabaja
