import type { ReactNode } from 'react'
import { motion } from 'framer-motion'
import { motionTiming, revealVariants } from './motion-config'

export function ScrollReveal({ children, className, delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  return <motion.div className={className} variants={revealVariants} initial="hidden" whileInView="show" viewport={{ once: true, amount: 0.16 }} transition={{ delay }}>{children}</motion.div>
}

export function ScaleReveal({ children, className }: { children: ReactNode; className?: string }) {
  return <motion.div className={className} initial={{ opacity: 0, scale: 0.97, y: 6 }} animate={{ opacity: 1, scale: 1, y: 0 }} transition={motionTiming.spring}>{children}</motion.div>
}

export function LoadingTransition({ children }: { children: ReactNode }) {
  return <motion.div role="status" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: motionTiming.fast }}>{children}</motion.div>
}

export function SuccessTransition({ children }: { children: ReactNode }) {
  return <motion.div initial={{ opacity: 0, scale: 0.94, y: 5 }} animate={{ opacity: 1, scale: 1, y: 0 }} transition={motionTiming.spring}>{children}</motion.div>
}

export function ErrorTransition({ children }: { children: ReactNode }) {
  return <motion.div initial={{ opacity: 0, x: 5 }} animate={{ opacity: 1, x: [5, -3, 2, 0] }} transition={{ duration: 0.28 }}>{children}</motion.div>
}

export function AnimatedModal({ children, className }: { children: ReactNode; className?: string }) {
  return <motion.section className={className} initial={{ opacity: 0, y: 12, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 8, scale: 0.98 }} transition={motionTiming.spring}>{children}</motion.section>
}
