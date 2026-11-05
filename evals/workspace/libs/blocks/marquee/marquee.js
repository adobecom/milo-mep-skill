function decorateButtons(el) {
  el.querySelectorAll('em a, strong a').forEach((link) => {
    const strong = link.closest('strong');
    link.classList.add('con-button', strong ? 'blue' : 'outline');
  });
  const actions = el.querySelector('p:has(.con-button)');
  actions?.classList.add('action-area');
}

export default function init(el) {
  const rows = [...el.querySelectorAll(':scope > div')];
  const foreground = rows.at(-1);
  foreground.classList.add('foreground');
  foreground.querySelector(':scope > div')?.classList.add('text');
  if (rows.length > 1) rows[0].classList.add('background');
  decorateButtons(foreground);
}
