'use strict';
document.querySelectorAll('.infra-image-control').forEach(control => {
  let frame;
  control.querySelector('.infra-select-image').addEventListener('click', () => {
    if (!frame) {
      frame = wp.media({ title: 'Fotografía de la taberna', button: { text: 'Usar esta fotografía' }, library: { type: 'image' }, multiple: false });
      frame.on('select', () => {
        const image = frame.state().get('selection').first().toJSON();
        control.querySelector('input').value = image.id;
        const preview = document.createElement('img');
        preview.src = image.sizes?.medium?.url || image.url;
        preview.alt = image.alt || '';
        control.querySelector('.infra-image-preview').replaceChildren(preview);
      });
    }
    frame.open();
  });
  control.querySelector('.infra-clear-image').addEventListener('click', () => {
    control.querySelector('input').value = '0';
    control.querySelector('.infra-image-preview').replaceChildren();
  });
});
const hours = document.getElementById('infra-hours');
if (hours) {
  let nextIndex = hours.children.length;
  document.getElementById('infra-add-hours').addEventListener('click', () => {
    if (hours.children.length >= 20) return;
    const html = document.getElementById('infra-hours-template').innerHTML.replaceAll('__INDEX__', String(nextIndex++));
    hours.insertAdjacentHTML('beforeend', html);
    hours.lastElementChild.querySelector('input').focus();
  });
  hours.addEventListener('click', event => {
    const button = event.target.closest('.infra-remove-hours');
    if (button) button.closest('.infra-hours-row').remove();
  });
}
