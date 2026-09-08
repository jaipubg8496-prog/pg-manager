const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// ---------- Build the isometric building from floor + window divs ----------

function buildBuilding(floorCount = 4) {
  const container = document.getElementById("building");
  const frontWindowLeft = [15, 70, 125, 180];
  const sideWindowLeft = [15, 60, 105];

  for (let i = 0; i < floorCount; i++) {
    const floorEl = document.createElement("div");
    floorEl.className = "floor";
    floorEl.style.top = `${-(i * 74)}px`;

    const front = document.createElement("div");
    front.className = "face face-front";
    frontWindowLeft.forEach((left) => {
      const w = document.createElement("div");
      w.className = "window " + (Math.random() > 0.42 ? "lit" : "dim");
      w.style.left = `${left}px`;
      front.appendChild(w);
    });

    const side = document.createElement("div");
    side.className = "face face-side";
    sideWindowLeft.forEach((left) => {
      const w = document.createElement("div");
      w.className = "window side " + (Math.random() > 0.55 ? "lit" : "dim");
      w.style.left = `${left}px`;
      side.appendChild(w);
    });

    floorEl.appendChild(front);
    floorEl.appendChild(side);
    container.appendChild(floorEl);
  }

  // Roof cap sits on top of the highest floor
  const roofWrap = document.createElement("div");
  roofWrap.className = "floor";
  roofWrap.style.top = `${-(floorCount * 74)}px`;
  const roof = document.createElement("div");
  roof.className = "face face-roof";
  roofWrap.appendChild(roof);
  container.appendChild(roofWrap);
}

// ---------- Build the phone mockup room grid ----------

function buildPhoneGrid() {
  const grid = document.getElementById("ps-grid");
  const rooms = [
    { label: "101", status: "busy", text: "Amit" },
    { label: "102", status: "free", text: "Vacant" },
    { label: "103", status: "busy", text: "Rohan" },
    { label: "104", status: "busy", text: "Karan" },
    { label: "105", status: "free", text: "Vacant" },
    { label: "106", status: "busy", text: "Ayesha" },
    { label: "107", status: "busy", text: "Priya" },
    { label: "108", status: "free", text: "Vacant" },
    { label: "109", status: "busy", text: "Zoya" },
  ];
  grid.innerHTML = rooms.map(r => `<div class="ps-tile ${r.status}">${r.label}<br>${r.text}</div>`).join("");
}

// ---------- Mouse parallax on the 3D building (interaction-triggered, so it's welcome motion) ----------

function enableParallax() {
  if (prefersReducedMotion) return;

  const scene = document.getElementById("scene");
  const rig = document.getElementById("rig");
  let ticking = false;

  scene.addEventListener("mousemove", (e) => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => {
      const rect = scene.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width - 0.5;
      const y = (e.clientY - rect.top) / rect.height - 0.5;
      const rotY = 32 + x * 18;
      const rotX = -14 - y * 10;
      rig.style.transform = `translate3d(0,0,0) rotateX(${rotX}deg) rotateY(${rotY}deg) scale(1.18)`;
      ticking = false;
    });
  });

  scene.addEventListener("mouseleave", () => {
    rig.style.transform = "translate3d(0,0,0) rotateX(-14deg) rotateY(32deg) scale(1.18)";
  });
}

buildBuilding(4);
buildPhoneGrid();

if (prefersReducedMotion) {
  enableParallax(); // no-op, guarded internally
} else {
  const rig = document.getElementById("rig");
  rig.addEventListener("animationend", enableParallax, { once: true });
}
