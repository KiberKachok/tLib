// Описание: Сервис справочников для фронтенда. Выполняет фоновую проверку версии справочных списков через
//           GET /api/reference-version (без кэширования), и при изменении версии обновляет списки (ДопШифр/РайонОбщий/Тип/Категории)
//           с 1 повторной попыткой при ошибке. UI не блокируется: обновление выполняется в фоне, а при устойчивой ошибке
//           (после 2 попыток) показывается sticky-сообщение через errorHandler, при этом в <select> остаются предыдущие значения.
//           Вместо прямого вызова UIController эмитирует событие reference:lists-loaded через appState.
//           Перенесён из js/modules/ в слой js/services/.
//           Та же проверка сравнивает started_at (время запуска сервера): сменился — сайт перезапущен,
//           вкладка работает на старом коде, показывается sticky-просьба обновить страницу и проверки
//           прекращаются. Иначе следующее обновление списков (version при рестарте тоже новый) сняло бы
//           просьбу через clearSticky — sticky-слот один.

import { CONSTANTS } from '../config/constants.js';
import { errorHandler } from '../core/errorHandler.js';
import { appState } from '../core/appState.js';
import { sleep } from '../utils/freeze.js';
import { fetchApiJsonSafe } from '../utils/fetchUtils.js';

const state = {
    initialized: false,
    currentVersion: null,
    startedAt: null,
    siteUpdated: false,
    lastCheckAt: 0,
    inFlightCheck: null,
    lastGoodLists: null
};

function isDocumentVisible() {
    try {
        return document.visibilityState === 'visible';
    } catch {
        return true;
    }
}

function nowMs() {
    return Date.now();
}

async function fetchReferenceVersion() {
    const res = await fetchApiJsonSafe(CONSTANTS.API.REFERENCE_VERSION, { cache: 'no-store' }, { retries: 0 });
    if (!res.ok) return res;
    return { ok: true, version: res.json.version ?? null, startedAt: res.json.started_at ?? null };
}

async function fetchList(endpoint) {
    const res = await fetchApiJsonSafe(endpoint, { cache: 'no-store' }, { retries: 0 });
    if (!res.ok) return res;
    if (!Array.isArray(res.json.data)) {
        return { ok: false, error: 'Bad list payload' };
    }
    return { ok: true, data: res.json.data };
}

async function fetchAllListsOnce() {
    const [dopshifr, raion, tip, kategoria] = await Promise.all([
        fetchList(CONSTANTS.API.DOPSHIFR_LIST),
        fetchList(CONSTANTS.API.RAION_OBSHIY_LIST),
        fetchList(CONSTANTS.API.TIP_LIST),
        fetchList(CONSTANTS.API.KATEGORIA_LIST)
    ]);

    const failures = [
        !dopshifr.ok ? `ДопШифр: ${dopshifr.error}` : null,
        !raion.ok ? `РайонОбщий: ${raion.error}` : null,
        !tip.ok ? `Тип: ${tip.error}` : null,
        !kategoria.ok ? `Категории: ${kategoria.error}` : null
    ].filter(Boolean);

    if (failures.length) {
        return { ok: false, error: failures.join('; ') };
    }

    return {
        ok: true,
        lists: {
            dopshifr: dopshifr.data,
            raionObshiy: raion.data,
            tip: tip.data,
            kategoriaUnified: kategoria.data
        }
    };
}

function applyListsToUI(lists) {
    appState.setCategoryOrder(Array.isArray(lists.kategoriaUnified) ? lists.kategoriaUnified : []);
    appState.emit('reference:lists-loaded', { lists });
}

async function refreshListsWithRetry() {
    // 2 попытки: первая + один быстрый повтор
    for (let attempt = 1; attempt <= 2; attempt += 1) {
        const res = await fetchAllListsOnce();
        if (res.ok) {
            state.lastGoodLists = res.lists;
            applyListsToUI(res.lists);
            errorHandler.clearSticky?.();
            return { ok: true };
        }

        if (attempt === 1) {
            await sleep(CONSTANTS.TIMING.REFERENCE_RETRY_DELAY);
            continue;
        }

        // Устойчивая ошибка (после 2 попыток)
        errorHandler.setSticky?.(CONSTANTS.MESSAGES.REFERENCE_UPDATE_FAILED);
        console.warn('ReferenceListsService: refresh failed:', res.error);
        return { ok: false, error: res.error };
    }
}

async function maybeRefresh({ force = false } = {}) {
    // Сайт перезапущен — страница ждёт перезагрузки, проверять больше нечего
    if (state.siteUpdated) return;

    if (!force) {
        const elapsed = nowMs() - state.lastCheckAt;
        if (elapsed < CONSTANTS.TIMING.REFERENCE_CHECK_THROTTLE) return;
        if (!isDocumentVisible()) return;
    }

    if (state.inFlightCheck) return state.inFlightCheck;

    state.lastCheckAt = nowMs();
    state.inFlightCheck = (async () => {
        try {
            // Первый запуск: сразу пытаемся загрузить списки (не блокируя UI).
            if (!state.lastGoodLists) {
                await refreshListsWithRetry();
                const v = await fetchReferenceVersion();
                if (v.ok) {
                    state.currentVersion = v.version;
                    if (!state.startedAt) state.startedAt = v.startedAt;
                }
                return;
            }

            const v = await fetchReferenceVersion();
            if (!v.ok) {
                // Не показываем сообщение пользователю: просто попробуем позже.
                console.warn('ReferenceListsService: version check failed:', v.error);
                return;
            }

            // Первая проверка не удалась — время запуска запоминаем по первой удачной
            if (!state.startedAt) state.startedAt = v.startedAt;

            // До сравнения version: при рестарте он тоже новый, а обновление списков сняло бы просьбу
            if (v.startedAt && v.startedAt !== state.startedAt) {
                state.siteUpdated = true;
                errorHandler.setSticky?.(CONSTANTS.MESSAGES.SITE_UPDATED);
                return;
            }

            const newVersion = v.version;
            if (newVersion && newVersion !== state.currentVersion) {
                const refreshed = await refreshListsWithRetry();
                if (refreshed.ok) state.currentVersion = newVersion;
            }
        } finally {
            state.inFlightCheck = null;
        }
    })();

    return state.inFlightCheck;
}

function installTriggers() {
    document.addEventListener('visibilitychange', () => {
        if (isDocumentVisible()) {
            void maybeRefresh();
        }
    });

    setInterval(() => {
        if (!isDocumentVisible()) return;
        void maybeRefresh();
    }, CONSTANTS.TIMING.REFERENCE_CHECK_INTERVAL);
}

export const ReferenceListsService = Object.freeze({
    initialize() {
        if (state.initialized) return;
        state.initialized = true;

        try {
            installTriggers();
        } catch (error) {
            console.warn('ReferenceListsService: failed to install triggers:', error);
        }

        // Стартовая загрузка в фоне
        void maybeRefresh({ force: true });
    }
});
