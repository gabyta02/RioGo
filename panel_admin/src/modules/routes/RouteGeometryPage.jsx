import { useEffect, useMemo, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { length as turfLength } from "@turf/turf";
import { AdminActionButton, TimedAlert } from "../../core/ui/AdminControls";
import ConfirmDialog from "../../core/ui/ConfirmDialog";
import SearchBox from "../../core/ui/SearchBox";
import { MapPinIcon } from "../../core/ui/icons";
import { buscarSitiosRuta, guardarGeometriaRuta, obtenerGeometriaRuta } from "./routesService";
import { getApiErrorMessage } from "../../core/api/errors";
import WorkspaceShell, { WorkspaceSidebar } from "../../core/ui/WorkspaceShell";

const CENTER = [-78.6546, -1.6635];
const LINE_SOURCE = "route-stable-line";
const LINE_LAYER = "route-stable-line";
const LINE_HIT_LAYER = "route-stable-line-hit";

let sequence = 0;

const id = (prefix) => `${prefix}-${Date.now()}-${++sequence}`;
const toNumber = (value) => Number(value);
const coord = (lngLat) => ({
  longitud: Number(lngLat.lng.toFixed(6)),
  latitud: Number(lngLat.lat.toFixed(6)),
});
const vertexCoord = (vertex) => ({ longitud: vertex.longitud, latitud: vertex.latitud });
const lineData = (vertices) => ({
  type: "FeatureCollection",
  features:
    vertices.length > 1
      ? [
          {
            type: "Feature",
            properties: {},
            geometry: {
              type: "LineString",
              coordinates: vertices.map((vertex) => [vertex.longitud, vertex.latitud]),
            },
          },
        ]
      : [],
});
const label = (point) => {
  if (point.tipo === "inicio") return "Origen";
  if (point.tipo === "fin") return "Destino";
  return point.nombre_sitio || "Punto libre";
};
const isConnected = (point, vertices) => Boolean(point.vertexId && vertices.some((vertex) => vertex.id === point.vertexId));
const pointDistance = (a, b) => {
  const dx = a.longitud - b.longitud;
  const dy = a.latitud - b.latitud;
  return dx * dx + dy * dy;
};
const snapshotGeometry = (vertices, points) => ({
  vertices: vertices.map((vertex) => ({ ...vertex })),
  points: points.map((point) => ({ ...point })),
});
const serializeGeometry = (vertices, points) => JSON.stringify({
  vertices: vertices.map(({ latitud, longitud }) => ({ latitud, longitud })),
  points: points
    .map(({ vertexId, tipo, id_sitio, latitud, longitud }) => ({ vertexId, tipo, id_sitio, latitud, longitud }))
    .sort((a, b) => String(a.vertexId || "").localeCompare(String(b.vertexId || ""))),
});

function makeVertex(raw) {
  return {
    id: id("vertex"),
    longitud: toNumber(raw.longitud),
    latitud: toNumber(raw.latitud),
  };
}

function nearestOrderedVertex(point, vertices, fromIndex, toIndex) {
  let bestIndex = fromIndex;
  let bestDistance = Number.POSITIVE_INFINITY;

  for (let index = fromIndex; index <= toIndex; index += 1) {
    const distance = pointDistance(point, vertices[index]);
    if (distance < bestDistance) {
      bestDistance = distance;
      bestIndex = index;
    }
  }

  return bestIndex;
}

function assignLoadedPoints(apiPoints, vertices) {
  if (!apiPoints?.length) return [];

  const ordered = [...apiPoints].sort((a, b) => (a.orden || 0) - (b.orden || 0));
  let cursor = 0;

  return ordered.map((point, index) => {
    let vertex = null;

    if (vertices.length) {
      if (index === 0 || point.tipo === "inicio") {
        vertex = vertices[0];
        cursor = 0;
      } else if (index === ordered.length - 1 || point.tipo === "fin") {
        vertex = vertices[vertices.length - 1];
      } else {
        const firstMiddleIndex = vertices.length > 2 ? 1 : 0;
        const lastMiddleIndex = vertices.length > 2 ? vertices.length - 2 : vertices.length - 1;
        const minIndex = Math.min(Math.max(cursor + 1, firstMiddleIndex), lastMiddleIndex);
        const maxIndex = Math.max(minIndex, lastMiddleIndex);
        const nearestIndex = nearestOrderedVertex(
          { longitud: toNumber(point.longitud), latitud: toNumber(point.latitud) },
          vertices,
          minIndex,
          maxIndex,
        );
        vertex = vertices[nearestIndex];
        cursor = nearestIndex;
      }
    }

    return {
      id: id("point"),
      vertexId: vertex?.id || null,
      id_sitio: point.id_sitio || null,
      nombre_sitio: point.nombre_sitio || null,
      tipo: point.tipo || "libre",
      longitud: vertex ? vertex.longitud : toNumber(point.longitud),
      latitud: vertex ? vertex.latitud : toNumber(point.latitud),
    };
  });
}

function projectPointOnSegment(point, start, end) {
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const lengthSquared = dx * dx + dy * dy;
  if (!lengthSquared) return start;

  const t = Math.max(0, Math.min(1, ((point.x - start.x) * dx + (point.y - start.y) * dy) / lengthSquared));
  return {
    x: start.x + t * dx,
    y: start.y + t * dy,
  };
}

function nearestSegment(map, vertices, lngLat) {
  if (vertices.length < 2) return null;

  const click = map.project(lngLat);
  let best = null;

  vertices.slice(0, -1).forEach((vertex, index) => {
    const start = map.project([vertex.longitud, vertex.latitud]);
    const endVertex = vertices[index + 1];
    const end = map.project([endVertex.longitud, endVertex.latitud]);
    const projected = projectPointOnSegment(click, start, end);
    const dx = click.x - projected.x;
    const dy = click.y - projected.y;
    const distance = dx * dx + dy * dy;

    if (!best || distance < best.distance) {
      best = { index, distance, projected };
    }
  });

  if (!best) return null;
  const lngLatProjected = map.unproject(best.projected);
  return {
    index: best.index,
    coordinate: coord(lngLatProjected),
  };
}

function nearestRemovableVertex(map, vertices, points, lngLat) {
  const controlled = new Set(points.filter((point) => point.vertexId).map((point) => point.vertexId));
  const click = map.project(lngLat);
  let best = null;

  vertices.forEach((vertex, index) => {
    if (controlled.has(vertex.id) || index === 0 || index === vertices.length - 1) return;

    const projected = map.project([vertex.longitud, vertex.latitud]);
    const dx = click.x - projected.x;
    const dy = click.y - projected.y;
    const distance = dx * dx + dy * dy;

    if (!best || distance < best.distance) {
      best = { vertex, distance };
    }
  });

  return best && best.distance <= 20 * 20 ? best.vertex : null;
}

export default function RouteGeometryPage({ route, onBack }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const verticesRef = useRef([]);
  const pointsRef = useRef([]);
  const modeRef = useRef("none");
  const pointMarkersRef = useRef([]);
  const vertexMarkersRef = useRef([]);
  const undoStackRef = useRef([]);
  const savedGeometryRef = useRef(serializeGeometry([], []));

  const [vertices, setVertices] = useState([]);
  const [points, setPoints] = useState([]);
  const [mode, setMode] = useState("none");
  const [connectFrom, setConnectFrom] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [sites, setSites] = useState([]);
  const [pendingLeave, setPendingLeave] = useState(false);

  useEffect(() => {
    verticesRef.current = vertices;
  }, [vertices]);

  useEffect(() => {
    pointsRef.current = points;
  }, [points]);

  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);

  const vertexIndex = (vertexId, source = verticesRef.current) => source.findIndex((vertex) => vertex.id === vertexId);
  const connectedPoints = (sourcePoints = pointsRef.current, sourceVertices = verticesRef.current) =>
    sourcePoints
      .filter((point) => isConnected(point, sourceVertices))
      .sort((a, b) => vertexIndex(a.vertexId, sourceVertices) - vertexIndex(b.vertexId, sourceVertices));
  const displayPoints = useMemo(() => {
    const connected = connectedPoints(points, vertices);
    const connectedIds = new Set(connected.map((point) => point.id));
    return [...connected, ...points.filter((point) => !connectedIds.has(point.id))];
  }, [points, vertices]);
  const distance = useMemo(() => {
    if (vertices.length < 2) return 0;
    return turfLength(
      {
        type: "Feature",
        properties: {},
        geometry: {
          type: "LineString",
          coordinates: vertices.map((vertex) => [vertex.longitud, vertex.latitud]),
        },
      },
      { units: "kilometers" },
    );
  }, [vertices]);

  function syncLineSource(nextVertices = verticesRef.current) {
    mapRef.current?.getSource(LINE_SOURCE)?.setData(lineData(nextVertices));
  }

  function pushUndoSnapshot() {
    const current = snapshotGeometry(verticesRef.current, pointsRef.current);
    const currentSerialized = serializeGeometry(current.vertices, current.points);
    const last = undoStackRef.current.at(-1);

    if (last && serializeGeometry(last.vertices, last.points) === currentSerialized) {
      return;
    }

    undoStackRef.current = [...undoStackRef.current.slice(-39), current];
  }

  function normalize(nextPoints, nextVertices) {
    const connected = connectedPoints(nextPoints, nextVertices);
    return nextPoints.map((point) => {
      const index = connected.findIndex((connectedPoint) => connectedPoint.id === point.id);
      const linkedVertex = point.vertexId ? nextVertices.find((vertex) => vertex.id === point.vertexId) : null;
      const coordinates = linkedVertex ? vertexCoord(linkedVertex) : { longitud: point.longitud, latitud: point.latitud };

      if (index < 0) {
        return {
          ...point,
          ...coordinates,
          vertexId: linkedVertex ? linkedVertex.id : null,
          tipo: point.id_sitio ? "sitio" : "libre",
        };
      }

      return {
        ...point,
        ...coordinates,
        tipo: index === 0 ? "inicio" : index === connected.length - 1 ? "fin" : point.id_sitio ? "sitio" : "libre",
      };
    });
  }

  function commit(nextVertices, nextPoints, { recordHistory = true } = {}) {
    if (recordHistory && serializeGeometry(verticesRef.current, pointsRef.current) !== serializeGeometry(nextVertices, nextPoints)) {
      pushUndoSnapshot();
    }
    const normalized = normalize(nextPoints, nextVertices);
    verticesRef.current = nextVertices;
    pointsRef.current = normalized;
    setVertices(nextVertices);
    setPoints(normalized);
    syncLineSource(nextVertices);
  }

  function undoGeometryChange() {
    const previous = undoStackRef.current.pop();
    if (!previous) return;
    commit(previous.vertices, previous.points, { recordHistory: false });
    setError("");
  }

  function hasUnsavedChanges() {
    return serializeGeometry(verticesRef.current, pointsRef.current) !== savedGeometryRef.current;
  }

  function confirmLeave() {
    if (!hasUnsavedChanges()) {
      onBack();
      return;
    }
    setPendingLeave(true);
  }

  function liveMoveVertex(vertexId, nextCoordinate) {
    const nextVertices = verticesRef.current.map((vertex) => (vertex.id === vertexId ? { ...vertex, ...nextCoordinate } : vertex));
    const nextPoints = pointsRef.current.map((point) => (point.vertexId === vertexId ? { ...point, ...nextCoordinate } : point));
    verticesRef.current = nextVertices;
    pointsRef.current = nextPoints;
    syncLineSource(nextVertices);
  }

  function liveMoveLoosePoint(pointId, nextCoordinate) {
    pointsRef.current = pointsRef.current.map((point) => (point.id === pointId ? { ...point, ...nextCoordinate } : point));
  }

  function insertVertexAfter(index, nextCoordinate) {
    const vertex = { id: id("vertex"), ...nextCoordinate };
    const nextVertices = [...verticesRef.current.slice(0, index + 1), vertex, ...verticesRef.current.slice(index + 1)];
    commit(nextVertices, pointsRef.current);
    return vertex;
  }

  function createPoint(lngLat, trace = false) {
    const nextCoordinate = coord(lngLat);
    const vertex = { id: id("vertex"), ...nextCoordinate };
    const point = {
      id: id("point"),
      vertexId: trace ? vertex.id : null,
      id_sitio: null,
      nombre_sitio: null,
      tipo: "libre",
      ...nextCoordinate,
    };

    if (trace) {
      commit([...verticesRef.current, vertex], [...pointsRef.current, point]);
      return;
    }

    commit(verticesRef.current, [...pointsRef.current, point]);
  }

  function connectPoint(pointId) {
    if (!connectFrom) {
      setConnectFrom(pointId);
      return;
    }

    const first = pointsRef.current.find((point) => point.id === connectFrom);
    const second = pointsRef.current.find((point) => point.id === pointId);
    setConnectFrom(null);

    if (!first || !second || first.id === second.id) return;

    const firstVertex = first.vertexId && verticesRef.current.find((vertex) => vertex.id === first.vertexId);
    const secondVertex = second.vertexId && verticesRef.current.find((vertex) => vertex.id === second.vertexId);

    if (!verticesRef.current.length && !firstVertex && !secondVertex) {
      const start = { id: id("vertex"), longitud: first.longitud, latitud: first.latitud };
      const end = { id: id("vertex"), longitud: second.longitud, latitud: second.latitud };
      commit(
        [start, end],
        pointsRef.current.map((point) => {
          if (point.id === first.id) return { ...point, vertexId: start.id, ...vertexCoord(start) };
          if (point.id === second.id) return { ...point, vertexId: end.id, ...vertexCoord(end) };
          return point;
        }),
      );
      return;
    }

    const endpoint = firstVertex ? first : secondVertex ? second : null;
    const loose = firstVertex ? second : secondVertex ? first : null;
    const endpointIndex = endpoint ? vertexIndex(endpoint.vertexId) : -1;

    if (!endpoint || !loose || (endpointIndex !== 0 && endpointIndex !== verticesRef.current.length - 1)) {
      setError("Solo puedes conectar un punto suelto con el origen o destino actual.");
      return;
    }

    const nextVertex = { id: id("vertex"), longitud: loose.longitud, latitud: loose.latitud };
    const nextVertices =
      endpointIndex === 0 ? [nextVertex, ...verticesRef.current] : [...verticesRef.current, nextVertex];

    commit(
      nextVertices,
      pointsRef.current.map((point) => (point.id === loose.id ? { ...point, vertexId: nextVertex.id } : point)),
    );
  }

  function removeVertex(vertexId) {
    const nextVertices = verticesRef.current.filter((vertex) => vertex.id !== vertexId);
    const nextPoints = pointsRef.current.filter((point) => point.vertexId !== vertexId);
      commit(nextVertices, nextPoints, { recordHistory: false });
      savedGeometryRef.current = serializeGeometry(nextVertices, normalize(nextPoints, nextVertices));
  }

  function removePoint(pointId) {
    const point = pointsRef.current.find((currentPoint) => currentPoint.id === pointId);
    if (!point) return;

    if (point.vertexId) {
      removeVertex(point.vertexId);
      return;
    }

    commit(
      verticesRef.current,
      pointsRef.current.filter((currentPoint) => currentPoint.id !== pointId),
    );
  }

  function setEndpoint(pointId, which) {
    const point = pointsRef.current.find((currentPoint) => currentPoint.id === pointId);
    if (!point?.vertexId) {
      setError("Conecta el punto antes de definirlo como origen o destino.");
      return;
    }

    const at = vertexIndex(point.vertexId);
    const nextVertices = which === "inicio" ? verticesRef.current.slice(at) : verticesRef.current.slice(0, at + 1);
    const allowed = new Set(nextVertices.map((vertex) => vertex.id));
    commit(
      nextVertices,
      pointsRef.current.filter((currentPoint) => !currentPoint.vertexId || allowed.has(currentPoint.vertexId)),
    );
  }

  function addSite(site) {
    if (verticesRef.current.length < 2) {
      setError("Crea primero una ruta con dos puntos.");
      return;
    }

    const end = verticesRef.current.at(-1);
    const vertex = {
      id: id("vertex"),
      latitud: toNumber(site.latitud),
      longitud: toNumber(site.longitud),
    };
    const point = {
      id: id("point"),
      vertexId: vertex.id,
      id_sitio: site.id_sitio,
      nombre_sitio: site.nombre,
      tipo: "sitio",
      latitud: vertex.latitud,
      longitud: vertex.longitud,
    };

    commit([...verticesRef.current.slice(0, -1), vertex, end], [...pointsRef.current, point]);
  }

  async function save() {
    const attached = connectedPoints();
    const loose = pointsRef.current.filter((point) => !point.vertexId);

    if (loose.length) {
      setError("Conecta o elimina todos los puntos sueltos antes de guardar.");
      return;
    }

    if (verticesRef.current.length < 2 || attached.length < 2) {
      setError("La ruta necesita origen y destino.");
      return;
    }

    setSaving(true);
    try {
      await guardarGeometriaRuta(route.id_ruta, {
        linea: verticesRef.current.map(({ latitud, longitud }) => ({ latitud, longitud })),
        puntos: attached.map((point, order) => {
          const vertex = verticesRef.current.find((currentVertex) => currentVertex.id === point.vertexId);
          return {
            orden: order + 1,
            tipo: point.tipo,
            id_sitio: point.id_sitio,
            latitud: vertex.latitud,
            longitud: vertex.longitud,
          };
        }),
      });
      savedGeometryRef.current = serializeGeometry(verticesRef.current, pointsRef.current);
      undoStackRef.current = [];
      setSuccess("Geometría guardada correctamente.");
    } catch (caughtError) {
      setError(getApiErrorMessage(caughtError));
    } finally {
      setSaving(false);
    }
  }

  useEffect(() => {
    let active = true;

    obtenerGeometriaRuta(route.id_ruta)
      .then((data) => {
        if (!active) return;
        const nextVertices = (data.linea || []).map(makeVertex);
        const nextPoints = assignLoadedPoints(data.puntos || [], nextVertices);
        commit(nextVertices, nextPoints);
      })
      .catch((caughtError) => active && setError(getApiErrorMessage(caughtError)))
      .finally(() => active && setLoading(false));

    return () => {
      active = false;
    };
  }, [route.id_ruta]);

  useEffect(() => {
    function handleBeforeUnload(event) {
      if (!hasUnsavedChanges()) return;
      event.preventDefault();
      event.returnValue = "";
    }

    function handleUndo(event) {
      const target = event.target;
      const isTyping =
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target?.isContentEditable;

      if (isTyping) return;

      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z" && !event.shiftKey) {
        event.preventDefault();
        undoGeometryChange();
      }
    }

    window.addEventListener("beforeunload", handleBeforeUnload);
    window.addEventListener("keydown", handleUndo);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
      window.removeEventListener("keydown", handleUndo);
    };
  }, []);

  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {
      buscarSitiosRuta(query)
        .then((results) => active && setSites(results))
        .catch(() => {});
    }, 250);

    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [query]);

  useEffect(() => {
    if (!containerRef.current) return undefined;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: "https://tiles.openfreemap.org/styles/liberty",
      center: CENTER,
      zoom: 13,
    });
    map.addControl(new maplibregl.NavigationControl(), "top-left");
    mapRef.current = map;

    map.on("load", () => {
      map.addSource(LINE_SOURCE, { type: "geojson", data: lineData(verticesRef.current) });
      map.addLayer({
        id: LINE_LAYER,
        type: "line",
        source: LINE_SOURCE,
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#1682c5", "line-width": 4 },
      });
      map.addLayer({
        id: LINE_HIT_LAYER,
        type: "line",
        source: LINE_SOURCE,
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#1682c5", "line-opacity": 0, "line-width": 22 },
      });
    });

    map.on("contextmenu", LINE_HIT_LAYER, (event) => {
      if (modeRef.current !== "edit") return;
      event.preventDefault?.();
      event.originalEvent?.preventDefault?.();
      const vertex = nearestRemovableVertex(map, verticesRef.current, pointsRef.current, event.lngLat);
      if (vertex) {
        removeVertex(vertex.id);
        return;
      }

      const insertion = nearestSegment(map, verticesRef.current, event.lngLat);
      if (!insertion) return;
      insertVertexAfter(insertion.index, insertion.coordinate);
    });

    map.on("click", LINE_HIT_LAYER, (event) => {
      if (modeRef.current !== "edit") return;
      const insertion = nearestSegment(map, verticesRef.current, event.lngLat);
      if (!insertion) return;
      insertVertexAfter(insertion.index, insertion.coordinate);
    });

    map.on("mouseenter", LINE_HIT_LAYER, () => {
      if (modeRef.current === "edit") map.getCanvas().style.cursor = "copy";
    });

    map.on("mouseleave", LINE_HIT_LAYER, () => {
      map.getCanvas().style.cursor = "";
    });

    map.on("click", (event) => {
      if (modeRef.current === "point") {
        createPoint(event.lngLat);
        setMode("none");
        return;
      }

      if (modeRef.current === "trace") {
        createPoint(event.lngLat, true);
      }
    });

    return () => {
      pointMarkersRef.current.forEach((marker) => marker.remove());
      vertexMarkersRef.current.forEach((marker) => marker.remove());
      map.remove();
    };
  }, []);

  useEffect(() => {
    syncLineSource(vertices);
  }, [vertices]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    pointMarkersRef.current.forEach((marker) => marker.remove());
    const ordered = displayPoints;
    const orderById = new Map(ordered.map((point, index) => [point.id, index + 1]));

    pointMarkersRef.current = ordered.map((point) => {
      const element = document.createElement("button");
      element.type = "button";
      element.className = "route-point-marker";
      element.dataset.type = point.tipo;
      element.dataset.loose = point.vertexId ? "false" : "true";
      element.textContent = String(orderById.get(point.id));

      element.onclick = (event) => {
        event.stopPropagation();
        const body = document.createElement("div");
        body.className = "route-point-popup";

        const title = document.createElement("p");
        title.textContent = label(point);
        body.append(title);

        [
          [connectFrom === point.id ? "Cancelar conexión" : "Conectar", () => (connectFrom === point.id ? setConnectFrom(null) : connectPoint(point.id))],
          ["Definir como origen", () => setEndpoint(point.id, "inicio")],
          ["Definir como destino", () => setEndpoint(point.id, "fin")],
          ["Eliminar marcador", () => removePoint(point.id)],
        ].forEach(([text, action]) => {
          const button = document.createElement("button");
          button.type = "button";
          button.textContent = text;
          button.onclick = () => {
            action();
            popup.remove();
          };
          body.append(button);
        });

        const popup = new maplibregl.Popup({ closeButton: true, offset: 16 })
          .setLngLat([point.longitud, point.latitud])
          .setDOMContent(body)
          .addTo(map);
      };

      const marker = new maplibregl.Marker({ element, draggable: !point.id_sitio })
        .setLngLat([point.longitud, point.latitud])
        .addTo(map);

      marker.on("drag", () => {
        const nextCoordinate = coord(marker.getLngLat());
        if (point.vertexId) liveMoveVertex(point.vertexId, nextCoordinate);
        else liveMoveLoosePoint(point.id, nextCoordinate);
      });

      marker.on("dragstart", pushUndoSnapshot);
      marker.on("dragend", () => {
        commit(verticesRef.current, pointsRef.current, { recordHistory: false });
      });

      return marker;
    });
  }, [displayPoints, connectFrom]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    vertexMarkersRef.current.forEach((marker) => marker.remove());
    vertexMarkersRef.current = [];

    if (mode !== "edit") return;

    const controlled = new Set(points.filter((point) => point.vertexId).map((point) => point.vertexId));
    const shapeVertexMarkers = vertices.flatMap((vertex, index) => {
      if (controlled.has(vertex.id) || index === 0 || index === vertices.length - 1) return [];

      const element = document.createElement("button");
      element.type = "button";
      element.className = "route-vertex-marker";
      element.title = "Arrastrar vertice. Clic derecho para eliminar.";
      element.textContent = "•";
      element.onclick = (event) => event.stopPropagation();
      element.oncontextmenu = (event) => {
        event.preventDefault();
        event.stopPropagation();
        removeVertex(vertex.id);
      };

      const marker = new maplibregl.Marker({ element, draggable: true })
        .setLngLat([vertex.longitud, vertex.latitud])
        .addTo(map);

      marker.on("dragstart", pushUndoSnapshot);
      marker.on("drag", () => {
        liveMoveVertex(vertex.id, coord(marker.getLngLat()));
      });
      marker.on("dragend", () => {
        commit(verticesRef.current, pointsRef.current, { recordHistory: false });
      });

      return [marker];
    });

    vertexMarkersRef.current = shapeVertexMarkers;
  }, [vertices, points, mode]);

  return (
    <>
      <WorkspaceShell
        actions={
          <>
            <AdminActionButton disabled={!undoStackRef.current.length || saving} onClick={undoGeometryChange}>
              Deshacer
            </AdminActionButton>
            <AdminActionButton variant="primary" disabled={saving} onClick={save}>
              {saving ? "Guardando..." : "Guardar geometría"}
            </AdminActionButton>
          </>
        }
        onBack={confirmLeave}
        subtitle={`${points.length} puntos · ${vertices.length} vértices · ${distance.toFixed(2)} km`}
        title={route.titulo}
      >
        <div className="grid min-h-0 flex-1 grid-cols-1 xl:h-full xl:grid-cols-[260px_minmax(0,1fr)_290px]">
        <WorkspaceSidebar title="Puntos">
          <p className="mb-4 text-xs font-bold text-app-texto-secundario">
            Crea puntos sueltos o traza una secuencia. Clic en un marcador para conectarlo, definir extremos o eliminarlo.
          </p>
          <button className="text-xs font-black text-app-error" type="button" onClick={() => commit([], [])}>
            Limpiar ruta
          </button>
          <div className="mt-4 space-y-2">
            {displayPoints.map((point, index) => (
              <div key={point.id} className="rounded-lg border border-app-borde p-3">
                <p className="font-black">
                  {index + 1}. {label(point)}
                </p>
                <p className="text-xs text-app-texto-secundario">
                  {point.vertexId ? `${point.latitud.toFixed(6)}, ${point.longitud.toFixed(6)}` : "Punto suelto"}
                </p>
              </div>
            ))}
            {!points.length && !loading ? <p className="text-sm text-app-texto-secundario">Crea un punto en el mapa.</p> : null}
          </div>
        </WorkspaceSidebar>

        <section className="relative min-h-[52vh]">
          <div ref={containerRef} className="h-full min-h-[52vh]" />
          <div className="absolute left-14 top-3 z-10 flex gap-2 rounded-lg bg-white p-2 shadow">
            <button
              className={`rounded px-3 py-2 text-xs font-black ${mode === "point" ? "bg-app-primario text-white" : "text-app-primario"}`}
              type="button"
              onClick={() => setMode(mode === "point" ? "none" : "point")}
            >
              Crear punto
            </button>
            <button
              className={`rounded px-3 py-2 text-xs font-black ${mode === "trace" ? "bg-app-primario text-white" : "text-app-primario"}`}
              type="button"
              onClick={() => setMode(mode === "trace" ? "none" : "trace")}
            >
              {mode === "trace" ? "Finalizar trazado" : "Trazar puntos"}
            </button>
            <button
              className={`rounded px-3 py-2 text-xs font-black ${mode === "edit" ? "bg-app-primario text-white" : "text-app-primario"}`}
              type="button"
              onClick={() => setMode(mode === "edit" ? "none" : "edit")}
            >
              Editar vértices
            </button>
          </div>
          <div className="absolute bottom-4 left-4 right-4">
            <TimedAlert onDismiss={() => setError("")}>{error}</TimedAlert>
            <TimedAlert variant="success" onDismiss={() => setSuccess("")}>
              {success}
            </TimedAlert>
          </div>
        </section>

        <WorkspaceSidebar title="Sitios">
          <SearchBox
            className="mb-4"
            label="Buscar sitio"
            placeholder="Buscar sitio..."
            value={query}
            onChange={setQuery}
          />
          {sites.map((site) => (
            <button
              key={site.id_sitio}
              className="mb-2 w-full rounded border border-app-borde p-3 text-left"
              type="button"
              onClick={() => addSite(site)}
            >
              <MapPinIcon /> <b>{site.nombre}</b>
            </button>
          ))}
        </WorkspaceSidebar>
        </div>
      </WorkspaceShell>
      {pendingLeave ? (
        <ConfirmDialog
          confirmLabel="Salir sin guardar"
          message="Hay cambios de geometría sin guardar. Si sales ahora, se perderán."
          onCancel={() => setPendingLeave(false)}
          onConfirm={onBack}
          title="Cambios sin guardar"
        />
      ) : null}
    </>
  );
}
