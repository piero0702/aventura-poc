import { deflateRawSync } from 'node:zlib';

export const columnasAventura = ['#', '@username', 'Nombre / Marca', 'Descripción', 'Categoría', 'Followers', 'Quality Audience', 'ER', 'Aud. Age', 'Aud. Gender', 'Audience City', 'Engagements', 'Avg. Likes', 'Avg. Comments', 'Avg. Reel Plays'];
const columnasAuditoria = ['Descartado', 'Encaje', 'Motivo de encaje', 'Notas', 'Costo USD', 'Seguidores de muestra', 'Marcas acreditadas', 'Fuente de audiencia'];
const escaparXml = (texto) => String(texto).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&apos;');
function columnaExcel(indice) {
  let salida = '';
  for (let numero = indice + 1; numero > 0; numero = Math.floor((numero - 1) / 26)) salida = String.fromCharCode(65 + (numero - 1) % 26) + salida;
  return salida;
}
function celda(valor, columna, fila) {
  const referencia = `${columnaExcel(columna)}${fila}`;
  if (valor === null || valor === undefined) return `<c r="${referencia}"/>`;
  if (typeof valor === 'number') return `<c r="${referencia}"><v>${valor}</v></c>`;
  return `<c r="${referencia}" t="inlineStr"><is><t xml:space="preserve">${escaparXml(valor)}</t></is></c>`;
}
const tablaCrc = Array.from({ length: 256 }, (_, indice) => {
  let valor = indice;
  for (let bit = 0; bit < 8; bit++) valor = valor & 1 ? 0xedb88320 ^ (valor >>> 1) : valor >>> 1;
  return valor >>> 0;
});
function crc32(datos) {
  let valor = 0xffffffff;
  for (const byte of datos) valor = tablaCrc[(valor ^ byte) & 255] ^ (valor >>> 8);
  return (valor ^ 0xffffffff) >>> 0;
}
function comprimirZip(archivos) {
  const partes = [];
  const directorio = [];
  let desplazamiento = 0;
  for (const [ruta, contenido] of archivos) {
    const nombre = Buffer.from(ruta);
    const origen = Buffer.from(contenido);
    const comprimido = deflateRawSync(origen);
    const crc = crc32(origen);
    const cabecera = Buffer.alloc(30);
    cabecera.writeUInt32LE(0x04034b50, 0);
    cabecera.writeUInt16LE(20, 4);
    cabecera.writeUInt16LE(8, 8);
    cabecera.writeUInt32LE(crc, 14);
    cabecera.writeUInt32LE(comprimido.length, 18);
    cabecera.writeUInt32LE(origen.length, 22);
    cabecera.writeUInt16LE(nombre.length, 26);
    partes.push(cabecera, nombre, comprimido);
    const entrada = Buffer.alloc(46);
    entrada.writeUInt32LE(0x02014b50, 0);
    entrada.writeUInt16LE(20, 4);
    entrada.writeUInt16LE(20, 6);
    entrada.writeUInt16LE(8, 10);
    entrada.writeUInt32LE(crc, 16);
    entrada.writeUInt32LE(comprimido.length, 20);
    entrada.writeUInt32LE(origen.length, 24);
    entrada.writeUInt16LE(nombre.length, 28);
    entrada.writeUInt32LE(desplazamiento, 42);
    directorio.push(entrada, nombre);
    desplazamiento += cabecera.length + nombre.length + comprimido.length;
  }
  const indice = Buffer.concat(directorio);
  const cierre = Buffer.alloc(22);
  cierre.writeUInt32LE(0x06054b50, 0);
  cierre.writeUInt16LE(archivos.length, 8);
  cierre.writeUInt16LE(archivos.length, 10);
  cierre.writeUInt32LE(indice.length, 12);
  cierre.writeUInt32LE(desplazamiento, 16);
  return Buffer.concat([...partes, indice, cierre]);
}
export function crearExcel(perfiles) {
  const filas = [[...columnasAventura, ...columnasAuditoria], ...perfiles.map((perfil) => [perfil.numero, `@${perfil.usuario}`, perfil.nombre, perfil.bio, perfil.categoria, perfil.followers, perfil.calidad_audiencia, perfil.metricas.er, perfil.audiencia.edad, perfil.audiencia.genero, perfil.audiencia.ciudad, perfil.metricas.engagements, perfil.metricas.likes, perfil.metricas.comentarios, perfil.metricas.reel_plays, perfil.descartado ? 'Sí' : 'No', perfil.encaje, perfil.motivo_encaje, perfil.notas.join(' · '), perfil.costo_usd, perfil.seguidores_muestra, perfil.marcas.map((marca) => marca.nombre).join(' · '), perfil.audiencia.fuente])];
  const hoja = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="A1:W${filas.length}"/><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols><col min="1" max="1" width="6" customWidth="1"/><col min="2" max="5" width="28" customWidth="1"/><col min="6" max="23" width="21" customWidth="1"/></cols><sheetData>${filas.map((fila, indice) => `<row r="${indice + 1}">${fila.map((valor, columna) => celda(valor, columna, indice + 1)).join('')}</row>`).join('')}</sheetData><autoFilter ref="A1:W${filas.length}"/></worksheet>`;
  return comprimirZip([
    ['[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'],
    ['_rels/.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'],
    ['xl/workbook.xml', '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Perfiles" sheetId="1" r:id="rId1"/></sheets></workbook>'],
    ['xl/_rels/workbook.xml.rels', '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>'],
    ['xl/worksheets/sheet1.xml', hoja],
  ]);
}
