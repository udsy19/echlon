import { motion } from "framer-motion";

/** Two very slow, very faint achromatic blobs (`bg-primary/5`, `blur-3xl`),
 *  moving on a 20–25s cycle. Parent must be `relative overflow-hidden`. */
export function BackgroundBlobs() {
  return (
    <div className="absolute inset-0 -z-10 pointer-events-none">
      <motion.div
        className="absolute top-1/4 -left-1/4 w-1/2 h-1/2 rounded-full bg-primary/5 blur-3xl"
        animate={{ x: [0, 50, 0], y: [0, 30, 0] }}
        transition={{ duration: 20, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute bottom-1/4 -right-1/4 w-1/2 h-1/2 rounded-full bg-primary/5 blur-3xl"
        animate={{ x: [0, -50, 0], y: [0, -30, 0] }}
        transition={{ duration: 25, repeat: Infinity, ease: "easeInOut" }}
      />
    </div>
  );
}
