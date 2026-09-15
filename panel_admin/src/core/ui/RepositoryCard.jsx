import EntityStatusBadge from "./EntityStatusBadge";
import EntityIcon from "./EntityIcon";
import { TableActionButton } from "./AdminControls";
import ExpandToggleButton from "./ExpandToggleButton";
import { text, layout } from "../typography";
import { ContentIcon, EditIcon, PlusIcon, RouteIcon, MapPinIcon, TrashIcon } from "./icons";

export default function RepositoryCard({
  documents,
  expanded,
  onAddContent,
  onCreateDocument,
  onDeleteDocument,
  onDeleteRepository,
  onEditDocument,
  onRenameRepository,
  onToggle,
  repository,
}) {
  const isRoute = repository.origen === "ruta";
  const Icon = isRoute ? RouteIcon : MapPinIcon;

  return (
    <section className="rounded-lg border border-app-borde bg-app-tarjeta shadow-sm">
      <div className={`flex flex-wrap items-center justify-between ${layout.cardGap} ${layout.cardPadding}`}>
        <button className={`flex min-w-0 items-center text-left ${layout.cardGap}`} type="button" onClick={onToggle}>
          <EntityIcon>
            <Icon />
          </EntityIcon>
          <span className="min-w-0">
            <span className={`flex flex-wrap items-center ${layout.cardGap}`}>
              <span className={text.entityTitle}>{repository.nombre}</span>
              <EntityStatusBadge active>{isRoute ? "Ruta" : "Sitio"}</EntityStatusBadge>
            </span>
            <span className={`mt-1 block ${text.entityMeta}`}>
              {repository.total_documentos} documentos
            </span>
          </span>
        </button>

        <div className="flex flex-wrap items-center gap-2">
          {onRenameRepository ? (
            <TableActionButton icon={<EditIcon />} onClick={onRenameRepository}>
              Renombrar
            </TableActionButton>
          ) : null}
          {onDeleteRepository ? (
            <TableActionButton icon={<TrashIcon />} variant="danger" onClick={onDeleteRepository}>
              Eliminar
            </TableActionButton>
          ) : null}
          {onCreateDocument ? (
            <TableActionButton icon={<PlusIcon />} onClick={onCreateDocument}>
              Crear documento
            </TableActionButton>
          ) : null}
          <ExpandToggleButton expanded={expanded} onClick={onToggle} size="sm" />
        </div>
      </div>

      {expanded ? (
        <div className="border-t border-app-borde bg-app-fondo/60">
          <div className="flex items-center justify-between px-4 py-3">
            <p className={text.sectionLabel}>Documentos</p>
            {onCreateDocument ? (
              <TableActionButton icon={<PlusIcon />} onClick={onCreateDocument}>
                Añadir
              </TableActionButton>
            ) : null}
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full border-collapse text-left text-sm">
              <thead className="bg-app-tarjeta text-xs font-black uppercase text-app-texto-secundario">
                <tr>
                  <th className="min-w-[420px] px-4 py-3">Documento</th>
                  <th className="px-4 py-3">Vínculo</th>
                  <th className="px-4 py-3">Estado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-app-borde bg-app-tarjeta">
                {documents.length ? (
                  documents.map((document) => (
                    <tr key={document.id_documento}>
                      <td className="px-4 py-3">
                        <div className="flex min-w-0 items-center gap-3">
                          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-app-primario-claro text-app-primario">
                            <ContentIcon />
                          </span>
                          <div className="min-w-0 flex-1">
                            <p className={text.entityTitle}>{document.titulo}</p>
                            <p className={`mt-1 line-clamp-2 ${text.entityMeta}`}>{document.descripcion}</p>
                            <p className={`mt-1 ${text.entityMeta}`}>
                              {document.ruta_archivo ? "Contenido agregado" : "Sin contenido agregado"}
                              {" · "}
                              {document.total_secciones || 0} secciones
                            </p>
                            <div className={`mt-3 flex flex-wrap items-center ${layout.cardGap}`}>
                              {onAddContent ? (
                                <TableActionButton
                                  icon={<ContentIcon />}
                                  variant={document.ruta_archivo ? "secondary" : "primary"}
                                  onClick={() => onAddContent(document)}
                                >
                                  {document.ruta_archivo ? "Editar contenido" : "Agregar contenido"}
                                </TableActionButton>
                              ) : null}
                              {onEditDocument ? (
                                <TableActionButton icon={<EditIcon />} onClick={() => onEditDocument(document)}>
                                  Editar datos
                                </TableActionButton>
                              ) : null}
                              {onDeleteDocument ? (
                                <TableActionButton
                                  icon={<TrashIcon />}
                                  variant="danger"
                                  onClick={() => onDeleteDocument(document)}
                                >
                                  Eliminar
                                </TableActionButton>
                              ) : null}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3 font-semibold text-app-texto-secundario">
                        {isRoute ? "Ruta" : "Sitio"}
                      </td>
                      <td className="px-4 py-3">
                        <EntityStatusBadge active={document.activo} />
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td className="px-4 py-8 text-center font-semibold text-app-texto-secundario" colSpan={3}>
                      No hay documentos registrados.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </section>
  );
}
