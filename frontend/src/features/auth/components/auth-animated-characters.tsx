"use client";

import { useEffect, useState } from "react";

type EyeProps = {
  size?: number;
  pupilSize?: number;
  maxDistance?: number;
  eyeColor?: string;
  pupilColor?: string;
  isBlinking?: boolean;
  lookX?: number;
  lookY?: number;
};

function Eye({
  size = 48,
  pupilSize = 16,
  maxDistance = 10,
  eyeColor = "white",
  pupilColor = "#1e293b",
  isBlinking = false,
  lookX = 0,
  lookY = 0,
}: EyeProps) {
  const pupilX = lookX * maxDistance;
  const pupilY = lookY * maxDistance;

  return (
    <div
      className="flex items-center justify-center overflow-hidden rounded-full transition-all duration-150"
      style={{
        width: `${size}px`,
        height: isBlinking ? "2px" : `${size}px`,
        backgroundColor: eyeColor,
      }}
    >
      {!isBlinking ? (
        <div
          className="rounded-full transition-transform duration-100 ease-out"
          style={{
            width: `${pupilSize}px`,
            height: `${pupilSize}px`,
            backgroundColor: pupilColor,
            transform: `translate(${pupilX}px, ${pupilY}px)`,
          }}
        />
      ) : null}
    </div>
  );
}

type PupilProps = {
  size?: number;
  maxDistance?: number;
  pupilColor?: string;
  lookX?: number;
  lookY?: number;
};

function Pupil({
  size = 12,
  maxDistance = 5,
  pupilColor = "#1e293b",
  lookX = 0,
  lookY = 0,
}: PupilProps) {
  return (
    <div
      className="rounded-full transition-transform duration-100 ease-out"
      style={{
        width: `${size}px`,
        height: `${size}px`,
        backgroundColor: pupilColor,
        transform: `translate(${lookX * maxDistance}px, ${lookY * maxDistance}px)`,
      }}
    />
  );
}

function useBlink() {
  const [isBlinking, setIsBlinking] = useState(false);

  useEffect(() => {
    let timeoutId: ReturnType<typeof setTimeout>;

    const scheduleBlink = () => {
      timeoutId = setTimeout(() => {
        setIsBlinking(true);
        timeoutId = setTimeout(() => {
          setIsBlinking(false);
          scheduleBlink();
        }, 140);
      }, Math.random() * 4000 + 3000);
    };

    scheduleBlink();
    return () => clearTimeout(timeoutId);
  }, []);

  return isBlinking;
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

export function AuthAnimatedCharacters() {
  const [lookX, setLookX] = useState(0);
  const [lookY, setLookY] = useState(0);
  const purpleBlinking = useBlink();
  const blackBlinking = useBlink();
  const isInteracting = lookX !== 0 || lookY !== 0;

  return (
    <>
      <style>{`
        @keyframes floatA { 0%,100%{transform:translateY(0)rotate(0deg)} 50%{transform:translateY(-18px)rotate(1.2deg)} }
        @keyframes floatB { 0%,100%{transform:translateY(0)rotate(0deg)} 50%{transform:translateY(-22px)rotate(-1deg)} }
        @keyframes floatC { 0%,100%{transform:translateY(0)rotate(0deg)} 50%{transform:translateY(-15px)rotate(1.8deg)} }
        @keyframes floatD { 0%,100%{transform:translateY(0)rotate(0deg)} 50%{transform:translateY(-20px)rotate(-1.4deg)} }
        .char-float-a { animation: floatA 3.4s ease-in-out infinite; transform-origin: bottom center; }
        .char-float-b { animation: floatB 3.0s ease-in-out infinite 0.7s; transform-origin: bottom center; }
        .char-float-c { animation: floatC 3.8s ease-in-out infinite 1.2s; transform-origin: bottom center; }
        .char-float-d { animation: floatD 3.2s ease-in-out infinite 0.4s; transform-origin: bottom center; }
        .char-interacting { animation: none !important; transition: transform 0.5s ease-out; }
      `}</style>
      <div
        className="relative h-[320px] w-[440px] max-w-full origin-bottom scale-[0.8] xl:h-[360px] xl:w-[500px] xl:scale-[0.92]"
        onMouseMove={(event) => {
          const rect = event.currentTarget.getBoundingClientRect();
          const relativeX = (event.clientX - rect.left) / rect.width;
          const relativeY = (event.clientY - rect.top) / rect.height;
          setLookX(clamp((relativeX - 0.5) * 2, -1, 1));
          setLookY(clamp((relativeY - 0.45) * 2, -1, 1));
        }}
        onMouseLeave={() => {
          setLookX(0);
          setLookY(0);
        }}
      >
      <div
        className={`absolute bottom-0 left-[70px] h-[400px] w-[180px] rounded-t-[10px] bg-[#6C3FF5] ${isInteracting ? "char-interacting" : "char-float-b"}`}
        style={isInteracting ? {
          transform: `skewX(${clamp(-lookX * 6, -6, 6)}deg)`,
          transformOrigin: "bottom center",
        } : undefined}
      >
        <div
          className="absolute flex gap-8 transition-all duration-200 ease-out"
          style={{
            left: `${45 + lookX * 15}px`,
            top: `${40 + lookY * 10}px`,
          }}
        >
          <Eye
            size={18}
            pupilSize={7}
            maxDistance={5}
            isBlinking={purpleBlinking}
            lookX={lookX}
            lookY={lookY}
          />
          <Eye
            size={18}
            pupilSize={7}
            maxDistance={5}
            isBlinking={purpleBlinking}
            lookX={lookX}
            lookY={lookY}
          />
        </div>
      </div>

      <div
        className={`absolute bottom-0 left-[240px] h-[310px] w-[120px] rounded-t-[8px] bg-[#2D2D2D] ${isInteracting ? "char-interacting" : "char-float-c"}`}
        style={isInteracting ? {
          transform: `skewX(${clamp(-lookX * 4.5, -6, 6)}deg)`,
          transformOrigin: "bottom center",
        } : undefined}
      >
        <div
          className="absolute flex gap-6 transition-all duration-200 ease-out"
          style={{
            left: `${26 + lookX * 12}px`,
            top: `${32 + lookY * 10}px`,
          }}
        >
          <Eye
            size={16}
            pupilSize={6}
            maxDistance={4}
            pupilColor="#2D2D2D"
            isBlinking={blackBlinking}
            lookX={lookX}
            lookY={lookY}
          />
          <Eye
            size={16}
            pupilSize={6}
            maxDistance={4}
            pupilColor="#2D2D2D"
            isBlinking={blackBlinking}
            lookX={lookX}
            lookY={lookY}
          />
        </div>
      </div>

      <div
        className={`absolute bottom-0 left-0 h-[200px] w-[240px] rounded-t-[120px] bg-[#FF9B6B] ${isInteracting ? "char-interacting" : "char-float-a"}`}
        style={isInteracting ? {
          transform: `skewX(${clamp(-lookX * 4, -6, 6)}deg)`,
          transformOrigin: "bottom center",
        } : undefined}
      >
        <div
          className="absolute flex gap-8 transition-all duration-200 ease-out"
          style={{
            left: `${82 + lookX * 14}px`,
            top: `${90 + lookY * 10}px`,
          }}
        >
          <Pupil lookX={lookX} lookY={lookY} />
          <Pupil lookX={lookX} lookY={lookY} />
        </div>
      </div>

      <div
        className={`absolute bottom-0 left-[310px] h-[230px] w-[140px] rounded-t-[70px] bg-[#E8D754] ${isInteracting ? "char-interacting" : "char-float-d"}`}
        style={isInteracting ? {
          transform: `skewX(${clamp(-lookX * 4, -6, 6)}deg)`,
          transformOrigin: "bottom center",
        } : undefined}
      >
        <div
          className="absolute flex gap-6 transition-all duration-200 ease-out"
          style={{
            left: `${52 + lookX * 12}px`,
            top: `${40 + lookY * 10}px`,
          }}
        >
          <Pupil lookX={lookX} lookY={lookY} />
          <Pupil lookX={lookX} lookY={lookY} />
        </div>
        <div
          className="absolute h-1 w-20 rounded-full bg-[#2D2D2D] transition-all duration-200 ease-out"
          style={{
            left: `${40 + lookX * 12}px`,
            top: `${88 + lookY * 10}px`,
          }}
        />
      </div>
    </div>
    </>
  );
}
