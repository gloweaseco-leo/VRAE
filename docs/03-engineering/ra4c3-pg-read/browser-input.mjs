// Wait for native scrolling/layout to settle before sending a real pointer event.
// In particular, a completed document load does not imply mobile scroll readiness.
export async function pointerPosition(ev, selector) {
  const target = JSON.stringify(selector);
  let previous;
  for (let attempt = 0; attempt < 150; attempt++) {
    const point = await ev(`(() => {
      const e = document.querySelector(${target});
      if (!e) throw Error('POINTER_TARGET_MISSING');
      const r = e.getBoundingClientRect();
      const x = r.x + r.width / 2, y = r.y + r.height / 2;
      const v = visualViewport;
      const inside = r.width > 0 && r.height > 0 && x >= 0 && y >= 0
        && x < innerWidth && y < innerHeight
        && (!v || (x >= v.offsetLeft && y >= v.offsetTop
          && x < v.offsetLeft + v.width && y < v.offsetTop + v.height));
      const hit = inside && document.elementFromPoint(x, y);
      const ready = !!hit && (hit === e || e.contains(hit));
      if (!ready) e.scrollIntoView({block: 'center', behavior: 'instant'});
      return {x, y, ready, scrollY};
    })()`);
    if (point.ready && previous?.ready
        && Math.abs(point.x - previous.x) < 0.5
        && Math.abs(point.y - previous.y) < 0.5
        && point.scrollY === previous.scrollY) {
      return {x: point.x, y: point.y};
    }
    previous = point;
    await new Promise(resolve => setTimeout(resolve, 40));
  }
  throw Error('POINTER_TARGET_NOT_STABLE_' + selector);
}
