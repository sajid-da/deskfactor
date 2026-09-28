import type { Variants } from 'framer-motion'

export const motionTiming = {
  fast: 0.16,
  standard: 0.32,
  page: 0.38,
  ease: [0.22, 1, 0.36, 1] as const,
  spring: { type: 'spring' as const, stiffness: 360, damping: 30, mass: 0.72 },
}

export const pageVariants: Variants = {
  hidden: { opacity: 0, y: 12, scale: 0.985 },
  show: { opacity: 1, y: 0, scale: 1, transition: { duration: motionTiming.page, ease: motionTiming.ease } },
  exit: { opacity: 0, y: -5, scale: 0.99, transition: { duration: motionTiming.fast, ease: 'easeIn' } },
}

export const revealVariants: Variants = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: motionTiming.standard, ease: motionTiming.ease } },
}

export const staggerVariants: Variants = {
  hidden: { opacity: 1 },
  show: { opacity: 1, transition: { staggerChildren: 0.075, delayChildren: 0.04 } },
}

export const staggerItemVariants: Variants = {
  hidden: { opacity: 0, y: 9 },
  show: { opacity: 1, y: 0, transition: { duration: motionTiming.standard, ease: motionTiming.ease } },
}
