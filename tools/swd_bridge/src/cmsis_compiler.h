// Minimal cmsis_compiler.h for building the CMSIS-DAP firmware sources on a Linux host (GCC/Clang).
#ifndef CMSIS_COMPILER_H_
#define CMSIS_COMPILER_H_

#ifndef __STATIC_INLINE
#define __STATIC_INLINE static inline
#endif
#ifndef __STATIC_FORCEINLINE
#define __STATIC_FORCEINLINE static inline __attribute__((always_inline))
#endif
#ifndef __WEAK
#define __WEAK __attribute__((weak))
#endif
#ifndef __ASM
#define __ASM __asm__
#endif
#ifndef __NOP
#define __NOP() __asm__ volatile("nop")
#endif

#endif  // CMSIS_COMPILER_H_
