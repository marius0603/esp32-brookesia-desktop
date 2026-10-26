#include <cstdarg>
#include <cstdio>
// ESP-SR 2.4.5 uses raw printf/puts from prebuilt libraries. Only this worker's
// diagnostic chatter is muted; other task console and panic paths stay intact.
bool offline_voice_worker_thread();
extern "C" int __real_puts(const char *);
extern "C" int __wrap_printf(const char *format,...) {
 if(offline_voice_worker_thread())return 0;
 va_list args;va_start(args,format);const int result=vprintf(format,args);va_end(args);return result;
}
extern "C" int __wrap_puts(const char *text){return offline_voice_worker_thread()?0:__real_puts(text);}
