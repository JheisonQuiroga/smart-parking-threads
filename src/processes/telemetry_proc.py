"""Proceso de telemetría (pendiente de implementar).

`TelemetryWorkerProcess(multiprocessing.Process)`: recibe eventos crudos por
`mp.Queue`, calcula métricas SO, delega la persistencia a `src/data` y envía
snapshots de vuelta al proceso principal.
"""
