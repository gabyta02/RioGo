from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field


class PreguntaMemoria(BaseModel):
    model_config = ConfigDict(extra="forbid")

    texto: str
    client_message_id: str
    registrado_en: str
    tipo: str | None = None
    resultado: str | None = None


class MemoriaPlanificador(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sesion_id: str
    preguntas: list[PreguntaMemoria] = Field(default_factory=list)
    entidades: list[str] = Field(default_factory=list)

    @classmethod
    def vacia(cls, sesion_id: str) -> "MemoriaPlanificador":
        return cls(sesion_id=sesion_id)

    def agregar_pregunta(
        self,
        texto: str,
        client_message_id: str,
        max_preguntas: int,
        *,
        tipo: str | None = None,
        resultado: str | None = None,
    ) -> None:
        pregunta = PreguntaMemoria(
            texto=texto.strip(),
            client_message_id=client_message_id,
            registrado_en=datetime.now(timezone.utc).isoformat(),
            tipo=tipo,
            resultado=resultado,
        )
        self.preguntas.insert(0, pregunta)
        if len(self.preguntas) > max_preguntas:
            self.preguntas = self.preguntas[:max_preguntas]


class TurnoMemoriaSitio(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pregunta: str
    respuesta: str
    client_message_id: str
    registrado_en: str


class MemoriaSitio(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sesion_id: str
    turnos: list[TurnoMemoriaSitio] = Field(default_factory=list)

    @classmethod
    def vacia(cls, sesion_id: str) -> "MemoriaSitio":
        return cls(sesion_id=sesion_id)

    def agregar_turno(
        self,
        *,
        pregunta: str,
        respuesta: str,
        client_message_id: str,
        max_turnos: int,
    ) -> None:
        turno = TurnoMemoriaSitio(
            pregunta=pregunta.strip(),
            respuesta=respuesta.strip(),
            client_message_id=client_message_id.strip(),
            registrado_en=datetime.now(timezone.utc).isoformat(),
        )
        self.turnos.insert(0, turno)
        if len(self.turnos) > max_turnos:
            self.turnos = self.turnos[:max_turnos]
