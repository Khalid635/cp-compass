/* 3D landing hero — a restrained compass: thin fuchsia rings, tick marks,
   a slowly settling needle, three orbiting dots, a faint particle field.
   R3F with frameloop="demand": a frame is requested only while the scene
   is mounted and visible (the Rig re-invalidates each frame; the wrapper
   kicks one frame when the hero scrolls back into view). No
   post-processing, no external models — primitives only, ~10 draw calls. */
import { useEffect, useLayoutEffect, useMemo, useRef } from 'react';
import * as THREE from 'three';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { Float } from '@react-three/drei';
import type { Theme } from '../hooks/useTheme';

export type HeroPointer = { x: number; y: number };

type SharedRefs = {
  pointerRef: { current: HeroPointer };
  pausedRef: { current: boolean };
  invalidateRef: { current: (() => void) | null };
};

type SceneProps = SharedRefs & {
  theme: Theme;
  onContextLost: () => void;
};

/* Exposes R3F's invalidate() to the wrapper so it can restart the
   demand loop when the hero scrolls back into view. */
function Kickstarter({ invalidateRef }: { invalidateRef: SharedRefs['invalidateRef'] }) {
  const invalidate = useThree((s) => s.invalidate);
  useEffect(() => {
    invalidateRef.current = invalidate;
    return () => {
      invalidateRef.current = null;
    };
  }, [invalidate, invalidateRef]);
  return null;
}

function Compass({
  theme,
  pointerRef,
  pausedRef,
}: {
  theme: Theme;
  pointerRef: SharedRefs['pointerRef'];
  pausedRef: SharedRefs['pausedRef'];
}) {
  const group = useRef<THREE.Group>(null!);
  const needle = useRef<THREE.Group>(null!);
  const orbit = useRef<THREE.Group>(null!);
  const ticks = useRef<THREE.InstancedMesh>(null!);

  /* Colours come from the design tokens (tokens.css) so the hero stays
     coherent with the rest of the app; the fallbacks match the tokens. */
  const primary = useMemo(
    () =>
      getComputedStyle(document.documentElement).getPropertyValue('--primary').trim() ||
      (theme === 'dark' ? '#e879f9' : '#a21caf'),
    [theme],
  );
  const muted = useMemo(
    () =>
      getComputedStyle(document.documentElement).getPropertyValue('--muted').trim() ||
      (theme === 'dark' ? '#b8a3ab' : '#6e5d66'),
    [theme],
  );

  const particles = useMemo(() => {
    const n = 140;
    const arr = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      const r = 1.2 + Math.random() * 2.6;
      const a = Math.random() * Math.PI * 2;
      arr[i * 3] = Math.cos(a) * r;
      arr[i * 3 + 1] = Math.sin(a) * r * 0.7;
      arr[i * 3 + 2] = (Math.random() - 0.5) * 0.8;
    }
    return arr;
  }, []);

  /* One instanced mesh for all 60 ticks — a single draw call. */
  useLayoutEffect(() => {
    const dummy = new THREE.Object3D();
    for (let i = 0; i < 60; i++) {
      const a = (i / 60) * Math.PI * 2;
      const long = i % 15 === 0;
      dummy.position.set(Math.sin(a) * 2.1, Math.cos(a) * 2.1, 0);
      dummy.rotation.set(0, 0, -a);
      dummy.scale.set(1, long ? 2 : 1, 1);
      dummy.updateMatrix();
      ticks.current.setMatrixAt(i, dummy.matrix);
    }
    ticks.current.instanceMatrix.needsUpdate = true;
  }, []);

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    const g = group.current;
    /* Slow dial drift + pointer parallax, eased toward the pointer. */
    g.rotation.z = Math.sin(t * 0.08) * 0.04;
    g.rotation.x = THREE.MathUtils.lerp(g.rotation.x, -0.42 + pointerRef.current.y * 0.08, 0.04);
    g.rotation.y = THREE.MathUtils.lerp(g.rotation.y, pointerRef.current.x * 0.16, 0.04);
    /* Needle settles like a real compass instead of spinning. */
    needle.current.rotation.z = Math.sin(t * 0.35) * 0.26 + Math.sin(t * 0.13) * 0.12;
    orbit.current.rotation.z = t * 0.06;
    if (!pausedRef.current) state.invalidate();
  });

  return (
    <group ref={group} rotation={[-0.42, 0, 0]} position={[0, 0.15, 0]}>
      <mesh>
        <torusGeometry args={[2.3, 0.012, 12, 160]} />
        <meshBasicMaterial color={primary} transparent opacity={0.55} />
      </mesh>
      <mesh>
        <torusGeometry args={[1.9, 0.006, 12, 128]} />
        <meshBasicMaterial color={primary} transparent opacity={0.25} />
      </mesh>
      <instancedMesh ref={ticks} args={[undefined, undefined, 60]}>
        <boxGeometry args={[0.012, 0.09, 0.012]} />
        <meshBasicMaterial color={primary} transparent opacity={0.4} />
      </instancedMesh>
      <group ref={needle}>
        <mesh position={[0, 0.75, 0]}>
          <coneGeometry args={[0.085, 1.5, 4]} />
          <meshBasicMaterial color={primary} transparent opacity={0.9} />
        </mesh>
        <mesh position={[0, -0.75, 0]} rotation={[0, 0, Math.PI]}>
          <coneGeometry args={[0.085, 1.5, 4]} />
          <meshBasicMaterial color={muted} transparent opacity={0.45} />
        </mesh>
        <mesh>
          <sphereGeometry args={[0.07, 16, 16]} />
          <meshBasicMaterial color={primary} />
        </mesh>
      </group>
      <Float speed={1.4} rotationIntensity={0} floatIntensity={0.5}>
        <group ref={orbit}>
          {[0, 2.1, 4.2].map((a, i) => (
            <mesh key={a} position={[Math.cos(a) * 2.62, Math.sin(a) * 2.62, 0.1]}>
              <sphereGeometry args={[0.05, 12, 12]} />
              <meshBasicMaterial
                color={i === 0 ? primary : muted}
                transparent
                opacity={i === 0 ? 0.95 : 0.6}
              />
            </mesh>
          ))}
        </group>
      </Float>
      <points>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[particles, 3]} />
        </bufferGeometry>
        <pointsMaterial size={0.035} color={primary} transparent opacity={0.35} sizeAttenuation />
      </points>
    </group>
  );
}

export default function HeroScene({
  theme,
  pointerRef,
  pausedRef,
  invalidateRef,
  onContextLost,
}: SceneProps) {
  return (
    <div className="absolute inset-0">
      <Canvas
        dpr={[1, 2]}
        frameloop="demand"
        gl={{ antialias: true, alpha: true, powerPreference: 'low-power' }}
        camera={{ position: [0, 0, 6.5], fov: 42 }}
        onCreated={({ gl }) => {
          gl.setClearColor(0x000000, 0);
          gl.domElement.addEventListener(
            'webglcontextlost',
            (e) => {
              e.preventDefault();
              onContextLost();
            },
            { once: true },
          );
        }}
      >
        <Kickstarter invalidateRef={invalidateRef} />
        <Compass theme={theme} pointerRef={pointerRef} pausedRef={pausedRef} />
      </Canvas>
    </div>
  );
}
