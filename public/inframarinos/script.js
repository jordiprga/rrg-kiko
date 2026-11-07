'use strict';
const tabs = [...document.querySelectorAll('[role="tab"]')];
function selectTab(tab) {
  tabs.forEach(item => {
    const selected = item === tab;
    item.setAttribute('aria-selected', String(selected));
    item.tabIndex = selected ? 0 : -1;
    document.getElementById(item.getAttribute('aria-controls')).hidden = !selected;
  });
}
tabs.forEach((tab, index) => {
  tab.addEventListener('click', () => selectTab(tab));
  tab.addEventListener('keydown', event => {
    let next;
    if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
    if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
    if (event.key === 'Home') next = 0;
    if (event.key === 'End') next = tabs.length - 1;
    if (next !== undefined) {
      event.preventDefault();
      selectTab(tabs[next]);
      tabs[next].focus();
    }
  });
});
const tapas = [
  'Universo 04 · Una Gilda abisal. La anchoa te mira. Tú no preguntes.',
  'Universo 19 · Croqueta de puchero. Aquí tu abuela es la jefa de cocina.',
  'Universo 08 · Berenjenas con miel de caña. En este mundo nunca se acaban.',
  'Universo 42 · Una ensaladilla que contiene la respuesta a todo. Y mayonesa.',
  'Universo 11 · Boquerones en vinagre. Han venido a Granada por el buen ambiente.',
  'Universo 03 · Patatas a lo pobre. En esta dimensión se llaman patatas con patrimonio.'
];
let previousTapa = -1;
document.getElementById('tapa-button').addEventListener('click', event => {
  const next = (previousTapa + 1 + Math.floor(Math.random() * (tapas.length - 1))) % tapas.length;
  previousTapa = next;
  document.getElementById('tapa-result').textContent = tapas[next];
  event.currentTarget.innerHTML = 'Otra ronda, otro universo <span>↗</span>';
});
document.getElementById('developer-joke').addEventListener('click', event => {
  const button = event.currentTarget;
  const expanded = button.getAttribute('aria-expanded') === 'true';
  button.setAttribute('aria-expanded', String(!expanded));
  document.getElementById('developer-note').hidden = expanded;
});
