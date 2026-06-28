// PaperFan — CSS recreation of the spiraling paper-fan motif.
// Stacked rounded rectangles rotating around a shared pivot, color
// interpolating from pale cream (top) to saturated gold (bottom).

// Expose React hooks globally so every text/babel file can use them
// (each Babel script gets its own scope — bare consts don't cross files).
window.useState = React.useState;
window.useEffect = React.useEffect;
window.useRef = React.useRef;

function lerp(a, b, t) { return a + (b - a) * t; }
function mixArr(c1, c2, t) {
  return [lerp(c1[0], c2[0], t), lerp(c1[1], c2[1], t), lerp(c1[2], c2[2], t)];
}
function rgb(c) { return `rgb(${Math.round(c[0])},${Math.round(c[1])},${Math.round(c[2])})`; }

function PaperFan({ count = 13, animate = true, pale = [251, 243, 197], gold = [255, 203, 61], startAngle = -10, sweep = 164, sizeScale = 1 }) {
  const black = [0, 0, 0];

  const cards = Array.from({ length: count }).map((_, i) => {
    const t = i / (count - 1);
    const tone = mixArr(pale, gold, Math.pow(t, 2.4));
    const bottom = mixArr(tone, black, 0.04 + 0.06 * t);
    const angle = startAngle + t * sweep;
    const delay = (count - i) * 0.035;
    return (
      <div
        key={i}
        className="pf-card"
        style={{
          background: `linear-gradient(155deg, ${rgb(tone)} 0%, ${rgb(bottom)} 100%)`,
          transform: `rotate(${angle}deg)`,
          zIndex: count - i,
          animationDelay: animate ? `${delay}s` : '0s',
          '--pf-angle': `${angle}deg`,
          '--pf-scale': sizeScale,
        }}
      />
    );
  });

  return (
    <div className={"pf-wrap" + (animate ? " pf-animate" : "")} aria-hidden="true">
      <div className="pf-depth pf-depth-1"></div>
      <div className="pf-depth pf-depth-2"></div>
      <div className="pf-depth pf-depth-3"></div>
      <div className="pf-pivot">{cards}</div>
    </div>
  );
}

window.PaperFan = PaperFan;
