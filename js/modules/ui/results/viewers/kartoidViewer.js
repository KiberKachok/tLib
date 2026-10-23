// Описание: Viewer-стратегия для 3D-карты треков (kartoid.com iframe). Реализует контракт viewer-стратегии:
//   buildFileListHtml, buildViewersHtml, autoLoad, getHashStateOnTabSwitch.
//   Фрейм сам берёт треки из /api/archive/…?original=1 (CORS — middlewares/kartoid_cors.py), без подготовки кеша.

import { CONSTANTS, TAB_TOKENS } from '../../../../config/constants.js';
import { escapeAttribute } from '../../../../utils/sanitize.js';
import { FileUtils } from '../../../fileUtils.js';
import { DataFormatter } from '../../dataFormatter.js';
import { activateViewerIframe, EXTERNAL_SVG } from './viewerHelpers.js';

/** Маппинг параметров Kartoid -> колонки отчёта */
const FIELDS = [
    ['route', 'Маршрут'], ['area', 'РайонОбщий'], ['region', 'Район'], ['type', 'Тип'], ['boat', 'ТипСудна'],
    ['grade', 'КатегорияС'], ['gradeTo', 'КатегорияПо'], ['year', 'Год'], ['month', 'МесяцС'], ['monthTo', 'МесяцПо'],
    ['author', 'Автор'], ['city', 'Город'], ['note', 'Комментарии'], ['uploaded', 'ДатаВремяЗагрузки'], ['uploader', 'ЗагрузилИмя'],
];

/**
 * Формирует URL Kartoid: треки, шифр и поля отчёта, ссылка на отчёт.
 * @param {string} baseUrl
 * @param {object[]} files
 * @param {{archiveName: string, row: object}} ctx
 * @returns {string}
 */
function buildKartoidUrl(baseUrl, files, { archiveName, row }) {
    const params = new URLSearchParams();
    files.forEach(file => {
        params.append('p', `${window.location.origin}${CONSTANTS.API.ARCHIVE_BASE}/${encodeURIComponent(archiveName)}/file/${encodeURIComponent(file.name)}?original=1`);
    });
    const { linkText, shareUrl } = DataFormatter.buildRowDownloadInfo(row);
    params.set('code', linkText);
    for (const [key, column] of FIELDS) {
        const value = String(row[column] ?? '').trim();
        if (value) params.set(key, value);
    }
    params.set('from', shareUrl);
    params.set('fromName', `Открыть отчёт на ${window.location.hostname}`);
    return `${baseUrl}?${params.toString()}`;
}

/**
 * Генерирует HTML содержимого file-list: ссылку на редактор Kartoid.
 * @param {object[]} files
 * @param {{shifr: string|number, dopShifr: string, archiveName: string, row: object}} ctx
 * @returns {string}
 */
export function buildFileListHtml(files, ctx) {
    const url = buildKartoidUrl(CONSTANTS.EXTERNAL_URLS.KARTOID_MAP, files, ctx);
    const windowName = FileUtils.makeWindowName(ctx.shifr, ctx.dopShifr, 'kartoid');
    return `<a href="${escapeAttribute(url)}" target="${escapeAttribute(windowName)}" rel="noopener">Открыть в редакторе Картоид ${EXTERNAL_SVG}</a>`;
}

/**
 * Генерирует HTML viewer-контейнера с kartoid.com iframe.
 * @param {object[]} files
 * @param {{archiveName: string, row: object}} ctx
 * @returns {string}
 */
export function buildViewersHtml(files, ctx) {
    const url = buildKartoidUrl(CONSTANTS.EXTERNAL_URLS.KARTOID_TRACK, files, ctx);

    return `<div class="viewer-container">
        <iframe referrerpolicy="no-referrer" class="viewer" title="Просмотр треков на kartoid.com" data-pending-url="${escapeAttribute(url)}" allow="clipboard-write; web-share; fullscreen; geolocation"></iframe>
    </div>`;
}

/**
 * Автоматически загружает карту при активации таба.
 * @param {HTMLElement} tabContent
 */
export function autoLoad(tabContent) {
    const iframe = tabContent?.querySelector('iframe[data-pending-url]');
    if (iframe) activateViewerIframe(iframe.parentElement, iframe, iframe.dataset.pendingUrl);
}

/**
 * Возвращает hash state при переключении на таб карты.
 * @returns {{tab: string}}
 */
export function getHashStateOnTabSwitch() {
    return { tab: TAB_TOKENS.MAP };
}
