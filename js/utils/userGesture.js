// Version 1.1 - 11.10.2026 09:17:47 GMT
// Описание: Промис «на странице был жест пользователя». Headless-боты исполняют наш JS,
//           но не двигают мышь и не касаются экрана, поэтому всё, что запускает конвертацию
//           PDF→PNG на сервере (cacheWarmService, pdfViewer), ждёт этот промис.
//           Слушатели ставятся при загрузке модуля, чтобы учесть жесты до первого вызова.
//           scroll намеренно не учитывается: его эмулируют скраперы для lazy-load.
//           Программный element.click() жестом не считается: он не порождает pointerdown.
// 1.1: hasUserGesture() — синхронная проверка: pdfViewer рисует кнопку «Открыть отчёт»
//      только тому, кто ещё не дал жеста.

const GESTURE_EVENTS = ['pointerdown', 'pointermove', 'wheel', 'touchstart', 'keydown'];

let happened = false;

const gesture = new Promise(resolve => {
    if (navigator.userActivation?.hasBeenActive) {
        happened = true;
        resolve();
        return;
    }
    const options = { capture: true, passive: true };
    const onGesture = () => {
        GESTURE_EVENTS.forEach(type => document.removeEventListener(type, onGesture, options));
        happened = true;
        resolve();
    };
    GESTURE_EVENTS.forEach(type => document.addEventListener(type, onGesture, options));
});

/**
 * Был ли жест пользователя к этому моменту (синхронно, без ожидания промиса).
 * @returns {boolean}
 */
export function hasUserGesture() {
    return happened;
}

/**
 * Возвращает общий промис, который резолвится при первом жесте пользователя.
 * @returns {Promise<void>}
 */
export function whenUserGesture() {
    return gesture;
}
