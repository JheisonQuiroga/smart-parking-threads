# GUIÓN TÉCNICO PARA VIDEO EXPLICATIVO (3 A 5 MINUTOS)
## Simulador de Parqueadero Inteligente — Concurrencia, Hilos, Locks, Semáforos y Multiprocessing

**Universidad EAN — Facultad de Ingeniería**  
**Asignatura**: Arquitectura de Computadores y Sistemas Operativos  
**Docente**: Diana Carolina Beltrán Peña  
**Duración Estimada**: 4 minutos y 30 segundos (Límite máximo: 5:00 min)  

---

### Recomendaciones previas para la grabación
1. **Resolución sugerida**: 1080p (1920x1080) a pantalla completa.
2. **Preparación de la pantalla**: Ten la aplicación abierta en Linux/Windows ejecutando `python3 main.py`. De fondo o en otra pestaña puedes tener abierto el editor de código (VS Code) en los archivos clave: [`parking_manager.py`](../src/core/parking_manager.py) y [`telemetry_proc.py`](../src/processes/telemetry_proc.py).
3. **Puntero del mouse**: Muévelo con calma para señalar cada panel cuando lo menciones.
4. **Tono de voz**: Seguro, pausado y técnico, demostrando dominio de los conceptos de Sistemas Operativos.

---

```
ESTRUCTURA DEL TIEMPO (TOTAL: ~4:30 min)
[0:00 - 0:40] Introducción, contexto académico y objetivo del proyecto
[0:40 - 1:40] Arquitectura de Procesos e Hilos (¿Cuáles son y qué rol cumplen?)
[1:40 - 2:40] Mecanismos de Sincronización: Semáforos y Locks en Exclusión Mutua
[2:40 - 4:00] Demostración en vivo de la simulación, métricas SO y registro de eventos
[4:00 - 4:30] Conclusiones y cierre formal
```

---

## BLOQUE 1: Introducción y Contexto Académico [0:00 – 0:40]

**Qué mostrar en pantalla:**  
Ventana principal del simulador abierta, limpia antes de iniciar, mostrando el título del proyecto y los paneles en reposo.

**Locución (Voz del estudiante):**
> *"Cordial saludo, profesora Diana Carolina y compañeros. Mi nombre es [Tu Nombre], estudiante de Ingeniería de la Universidad EAN. En este video presentaré la sustentación y demostración práctica de nuestro proyecto final para la asignatura de **Arquitectura de Computadores y Sistemas Operativos**: el **Simulador de Parqueadero Inteligente con Hilos, Multiprocesamiento y GUI en Python**.*
>
> *El objetivo principal de este desarrollo es representar visual y cuantitativamente cómo un **Sistema Operativo** administra un conjunto finito de recursos compartidos frente a múltiples procesos concurrentes que compiten por ellos, aplicando primitivos fundamentales de sincronización: **Hilos**, **Semáforos**, **Locks de Exclusión Mutua** y **Multiprocesamiento paralelo**."*

---

## BLOQUE 2: Procesos e Hilos en el Sistema Operativo [0:40 – 1:40]

**Qué mostrar en pantalla:**  
Señala con el cursor el panel *"Hilos de Ejecución (Vehículos)"* y, si deseas, muestra rápidamente el diagrama o el archivo `main.py` / `app_controller.py`.

**Locución (Voz del estudiante):**
> *"Para entender la arquitectura, primero definamos los dos niveles de concurrencia implementados:*
>
> 1. ***¿Qué son los Procesos y cuáles tenemos en el proyecto?***  
> *Un proceso es una instancia independiente de un programa en ejecución administrada directamente por el Sistema Operativo, con su propia memoria y su propia tabla de descriptores. En este proyecto no tenemos un solo proceso, sino **dos procesos del SO corriendo en paralelo real**:*
>    - *El **Proceso Principal**: aloja el ciclo de eventos de la interfaz gráfica en Tkinter y coordina los hilos concurrentes.*
>    - *El **Proceso Secundario (`TelemetryWorker`)**: creado con el módulo `multiprocessing`. Este proceso corre en otro núcleo de la CPU con su propio GIL (Global Interpreter Lock), recibiendo eventos a través de una cola IPC (`multiprocessing.Queue`) para calcular en tiempo real las métricas de rendimiento del SO y persistir los registros en archivos CSV sin ralentizar la interfaz.*
>
> 2. ***¿Qué son los Hilos y cuáles son en el simulador?***  
> *Un hilo es la unidad básica de ejecución que vive dentro de un proceso y comparte el mismo espacio de memoria. En nuestro sistema, **cada vehículo es un hilo independiente (`threading.Thread`)**. Cada uno tiene su propio ciclo de vida y emula fielmente los estados de un proceso en el SO: **Nuevo** al crearse, **Listo o Bloqueado** cuando solicita cupo, **En Ejecución** cuando está estacionado en servicio, y **Terminado** al liberar el cajón y salir."*

---

## BLOQUE 3: Mecanismos de Sincronización: Semáforos y Locks [1:40 – 2:40]

**Qué mostrar en pantalla:**  
Señala el panel de *"Plazas de Parqueo"* (los cajones 1 al 5) y luego la tabla de vehículos.

**Locución (Voz del estudiante):**
> *"Dado que múltiples hilos compiten al mismo tiempo por los cupos físicos del parqueadero, es obligatorio implementar mecanismos de sincronización para evitar colisiones e inconsistencias:*
>
> 1. ***¿Qué son los Semáforos y cómo los utilizamos?***  
> *Un semáforo es un primitivo de sincronización propuesto por Dijkstra que maneja un contador interno de recursos disponibles. En nuestro código utilizamos un `threading.BoundedSemaphore(CAPACIDAD)`. Su función es gobernar el aforo máximo del parqueadero (en este ejemplo, 5 cupos).*
> *Cuando un vehículo desea entrar, ejecuta `semaforo.acquire()`. Si el contador es mayor a cero, se decrementa y el vehículo pasa. Pero cuando el parqueadero llega a su capacidad máxima, el semáforo queda en cero y **bloquea de forma nativa a los siguientes hilos**, reteniéndolos en la cola de espera del sistema operativo sin consumir ciclos inútiles de CPU.*
>
> 2. ***¿Qué son los Locks y por qué son indispensables?***  
> *Un Lock o cerrojo es un mecanismo binario que garantiza la **Exclusión Mutua** en una **Sección Crítica** del código.*
> *¿Qué pasaría sin el Lock? Si dos hilos obtienen paso simultáneamente, ambos intentarían modificar la lista de cajones en el mismo milisegundo, produciendo una **condición de carrera (race condition)** donde dos vehículos se asignarían el mismo cajón físico o se corrompería el contador de ocupados.*
> *Para evitarlo, protegemos el acceso con `with lock:` en dos secciones críticas atómicas muy breves: una al **ingresar** para reclamar el cajón libre e incrementar `ocupados += 1`, y otra al **salir** para desocuparlo y decrementar `ocupados -= 1`. El Lock solo se retiene por microsegundos, permitiendo máxima concurrencia."*

---

## BLOQUE 4: Demostración en Vivo, Métricas del SO y Registro de Eventos [2:40 – 4:00]

**Qué hacer en pantalla:**  
1. Configuración: Deja Capacidad = 5, Vehículos = 8, Llegada = 0.5 a 4.0 s, Estadía = 3.0 a 8.0 s.
2. Haz clic en el botón verde **▶ Iniciar simulación**.
3. Mantén el cursor sobre la pantalla mostrando cómo se actualizan los componentes.

**Locución (Voz del estudiante):**
> *(Al hacer clic en Iniciar)*:  
> *"Veamos el sistema en acción. Al presionar 'Iniciar simulación', el sistema instancia los 8 hilos de vehículos y arranca el proceso de telemetría.*
>
> *(Señala los primeros cajones que se ocupan)*:  
> *Observen cómo los primeros vehículos despiertan, adquieren el semáforo y toman el Lock para ocupar los Cajones del 1 al 5. Los íconos cambian a rojo con el gráfico del vehículo indicando que la plaza está ocupada.*
>
> *(Señala la tabla y los vehículos bloqueados)*:  
> *En este momento, la ocupación llega a 5 de 5 (100%). Miren lo que sucede con los vehículos 6, 7 y 8: como el semáforo está en cero, sus estados pasan a 'Esperando cupo (Bloqueado)'. Sus hilos están suspendidos por el SO y sus tiempos de espera avanzan en vivo segundo a segundo en la tabla.*
>
> *(Señala cuando un vehículo sale y otro toma su lugar)*:  
> *¡Atención a este relevo! El Vehículo #2 terminó su estadía: entra a su sección crítica de salida, toma el Lock, desocupa el Cajón #2 y ejecuta `semaphore.release()`. En ese mismo instante, el semáforo despierta al primer vehículo que estaba en cola, el cual toma el Lock y se adueña del Cajón #2 recién liberado sin ninguna colisión.*
>
> *(Señala el panel de Métricas y el Registro de Eventos)*:  
> *En el panel superior vemos las métricas que nuestro proceso secundario calcula en tiempo real:*
> - *El **Tiempo de Espera Promedio**, que mide la latencia de los procesos en cola.*
> - *El **Tiempo de Servicio**, correspondiente al tiempo activo de CPU o estadía.*
> - *El **Tiempo de Retorno (Turnaround Time)**, que es la suma del tiempo de espera más el tiempo de servicio.*
> - *Y la **Utilización del Recurso**, que evalúa qué porcentaje del tiempo total los cajones estuvieron efectivamente ocupados.*
> *Por último, en el **Registro de Eventos** (de solo lectura) queda la auditoría cronológica exacta de cada adquisición de semáforo, toma de lock y liberación."*

---

## BLOQUE 5: Conclusiones y Cierre [4:00 – 4:30]

**Qué mostrar en pantalla:**  
La simulación terminando (todos los vehículos en estado `Salió (Terminado)` y los 5 cajones en verde `DISPONIBLE`), o la cámara enfocándote a ti.

**Locución (Voz del estudiante):**
> *"Como pudimos evidenciar en esta corrida:*
> 1. *El uso de **semáforos y cerrojos (Locks)** resolvió categóricamente el problema de la competencia por recursos finitos, evitando condiciones de carrera y sobreasignaciones.*
> 2. *La combinación de **hilos para tareas concurrentes livianas** y **multiprocesamiento para cómputo analítico y persistencia** demostró ser una arquitectura sólida y escalable, preservando la fluidez de la interfaz gráfica a 60 cuadros por segundo.*
> 3. *Este proyecto aterriza con total fidelidad los principios de planificación, sincronización y gestión de memoria que rigen a los Sistemas Operativos modernos.*
>
> *Muchas gracias por su atención."*

---

### Check-list antes de subir el video
- [ ] Duración total entre 3:00 y 4:59 minutos.
- [ ] Audio claro y sin ruido de fondo.
- [ ] Interfaz gráfica visible con textos nítidos.
- [ ] Enlace subido a **YouTube (como No Listado / Público)** o **Google Drive (con permisos: 'Cualquier persona con el enlace puede ver')**.
- [ ] Copiar y pegar el enlace resultante en la Sección 5 del [`informe.md`](informe.md) y en la entrega virtual.
