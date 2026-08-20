/**
 * NodiLogo Component.
 * Owner: P7
 *
 * Premium NODI network-nodes logo mark.
 * Features the signature stylized 'N' ribbon with electric cyan to vibrant purple gradient
 * and three interconnected luminous 3D nodes representing knowledge grounding.
 */

import React from "react";

interface NodiLogoProps {
  size?: number;
  className?: string;
}

export const NodiLogo: React.FC<NodiLogoProps> = ({
  size = 32,
  className = "",
}) => {
  const gradientId = React.useId();

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="NODI logo"
    >
      <defs>
        {/* Main Ribbon Gradient: Electric Cyan -> Vibrant Purple -> Deep Indigo */}
        <linearGradient
          id={`${gradientId}-ribbon`}
          x1="12"
          y1="16"
          x2="52"
          y2="52"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0%" stopColor="#00D4FF" />
          <stop offset="48%" stopColor="#6C5CE7" />
          <stop offset="100%" stopColor="#25406E" />
        </linearGradient>

        {/* Node 1 Glow (Cyan) */}
        <radialGradient
          id={`${gradientId}-node-cyan`}
          cx="35%"
          cy="35%"
          r="65%"
        >
          <stop offset="0%" stopColor="#70E5FF" />
          <stop offset="60%" stopColor="#00D4FF" />
          <stop offset="100%" stopColor="#0080FF" />
        </radialGradient>

        {/* Node 2 Glow (Cyan-Purple) */}
        <radialGradient
          id={`${gradientId}-node-purple`}
          cx="35%"
          cy="35%"
          r="65%"
        >
          <stop offset="0%" stopColor="#A29BFE" />
          <stop offset="60%" stopColor="#6C5CE7" />
          <stop offset="100%" stopColor="#4834D4" />
        </radialGradient>

        {/* Node 3 Grounded Answer Glow (Luminous Gold Accent) */}
        <radialGradient
          id={`${gradientId}-node-accent`}
          cx="35%"
          cy="35%"
          r="65%"
        >
          <stop offset="0%" stopColor="#FFEAA7" />
          <stop offset="55%" stopColor="var(--accent, #D9A75C)" />
          <stop offset="100%" stopColor="#B8863C" />
        </radialGradient>

        {/* Node Outer Drop Shadow */}
        <filter id={`${gradientId}-glow`} x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="1" stdDeviation="1.5" floodColor="#000000" floodOpacity="0.25" />
        </filter>
      </defs>

      {/* Stylized 'N' Ribbon Backbone */}
      <path
        d="M18 48V20C18 16.5 21 14 24.5 15.5L46 45.5V18"
        stroke={`url(#${gradientId}-ribbon)`}
        strokeWidth="6.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="opacity-95"
      />

      {/* Interconnecting Network Bridge Lines */}
      <line
        x1="14"
        y1="38"
        x2="48"
        y2="16"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeDasharray="1 0"
        opacity="0.45"
      />
      <line
        x1="48"
        y1="16"
        x2="48"
        y2="48"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeDasharray="1 0"
        opacity="0.45"
      />
      <line
        x1="14"
        y1="38"
        x2="48"
        y2="48"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeDasharray="1 0"
        opacity="0.45"
      />

      {/* Node 1: Left Mid Source Node (Electric Cyan Sphere) */}
      <g filter={`url(#${gradientId}-glow)`}>
        <circle
          cx="14"
          cy="38"
          r="5.5"
          fill={`url(#${gradientId}-node-cyan)`}
        />
        {/* 3D Specular Highlight Dot */}
        <circle cx="12.5" cy="36.5" r="1.5" fill="#FFFFFF" opacity="0.85" />
      </g>

      {/* Node 2: Top Right Source Node (Vibrant Purple Sphere) */}
      <g filter={`url(#${gradientId}-glow)`}>
        <circle
          cx="48"
          cy="16"
          r="6.5"
          fill={`url(#${gradientId}-node-purple)`}
        />
        {/* 3D Specular Highlight Dot */}
        <circle cx="46" cy="14" r="1.8" fill="#FFFFFF" opacity="0.9" />
      </g>

      {/* Node 3: Bottom Right Grounded Answer Node (Luminous Accent Sphere) */}
      <g filter={`url(#${gradientId}-glow)`}>
        <circle
          cx="48"
          cy="48"
          r="7"
          fill={`url(#${gradientId}-node-accent)`}
        />
        {/* 3D Specular Highlight Dot */}
        <circle cx="45.8" cy="45.8" r="2" fill="#FFFFFF" opacity="0.9" />
      </g>
    </svg>
  );
};

export default NodiLogo;
