from typing import Literal, Union

from pydantic import BaseModel, Field, field_validator

from esquemas.chatboot_comun import EstadoBusqueda, FiltroIdsConsulta

TipoHorarioConsulta = Literal[
    "instantaneo",
    "punto_tiempo",
    "bloque_tiempo",
    "relacional",
    "dias_solamente",
]
ComparadorHorarioConsulta = Literal["", "igual", "dentro_de", "mayor_que", "menor_que"]


class HorarioConsultaEntrada(FiltroIdsConsulta):
    tipo: TipoHorarioConsulta
    dia_semana: int | None = None
    dias_semana: list[int] | None = None
    hora: str | None = None
    rango_hora: list[str] | None = None
    comparador: ComparadorHorarioConsulta = ""
    excluir_dias: list[int] = Field(default_factory=list)

    @field_validator("dia_semana")
    @classmethod
    def validar_dia_semana(cls, valor: int | None) -> int | None:
        if valor is None:
            return None
        if not 1 <= valor <= 7:
            raise ValueError("dia_semana debe estar entre 1 y 7.")
        return valor

    @field_validator("dias_semana")
    @classmethod
    def validar_dias_semana(cls, valor: list[int] | None) -> list[int] | None:
        if valor is None:
            return None
        dias: list[int] = []
        for dia in valor:
            if not 1 <= dia <= 7:
                raise ValueError("dias_semana solo admite valores entre 1 y 7.")
            if dia not in dias:
                dias.append(dia)
        return dias

    @field_validator("hora")
    @classmethod
    def validar_hora(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        texto = valor.strip()
        partes = texto.split(":")
        if len(partes) not in {2, 3} or not all(parte.isdigit() for parte in partes):
            raise ValueError("hora debe tener formato HH:MM.")
        hora, minuto = int(partes[0]), int(partes[1])
        if not (0 <= hora <= 23 and 0 <= minuto <= 59):
            raise ValueError("hora debe tener formato HH:MM válido.")
        return f"{hora:02d}:{minuto:02d}"

    @field_validator("rango_hora")
    @classmethod
    def validar_rango_hora(cls, valor: list[str] | None) -> list[str] | None:
        if valor is None:
            return None
        if len(valor) != 2:
            raise ValueError("rango_hora debe contener exactamente dos valores HH:MM.")
        inicio = cls.validar_hora(valor[0])
        fin = cls.validar_hora(valor[1])
        if inicio is None or fin is None:
            raise ValueError("rango_hora debe contener horas válidas HH:MM.")
        return [inicio, fin]

    @field_validator("excluir_dias")
    @classmethod
    def validar_excluir_dias(cls, valor: list[int]) -> list[int]:
        for dia in valor:
            if not 1 <= dia <= 7:
                raise ValueError("excluir_dias solo admite valores entre 1 y 7.")
        return valor


class CandidatoHorarioItem(BaseModel):
    id_sitio: int
    abierto_24h: bool = False
    horario_texto: str = ""
    comentario: str | None = None
    cumplimiento_condicional: bool = False
    dias_semana_resueltos: list[int] = Field(default_factory=list)
    hora_consultada: str | None = None
    criterio_cumplido: bool = False


class HorarioConsultaExito(BaseModel):
    ids_sitio: list[int]
    candidatos: list[CandidatoHorarioItem] = Field(default_factory=list)
    estado_busqueda: EstadoBusqueda | None = None


class HorarioConsultaSinSitios(BaseModel):
    sin_sitios: str
    candidatos: list[CandidatoHorarioItem] = Field(default_factory=list)
    estado_busqueda: EstadoBusqueda | None = None


class HorarioConsultaFallo(BaseModel):
    fallo: str
    estado_busqueda: EstadoBusqueda | None = None


HorarioConsultaSalida = Union[
    HorarioConsultaExito,
    HorarioConsultaSinSitios,
    HorarioConsultaFallo,
]
