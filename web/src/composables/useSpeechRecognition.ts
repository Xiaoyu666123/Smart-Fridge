/**
 * 浏览器原生语音识别封装（Web Speech API）。
 *
 * 兼容性：Chrome / Edge / 国内套壳浏览器原生支持，Firefox / 部分 Safari 不支持。
 * 不支持时返回 supported=false，调用方应隐藏麦克风按钮。
 *
 * 用法：
 *   const { supported, listening, interim, start, stop, toggle, error } = useSpeechRecognition({
 *     lang: 'zh-CN',
 *     continuous: true,
 *     onFinal: (text) => { ... },     // 一段稳定结果出来时
 *     onInterim: (text) => { ... },   // 临时结果（边说边变）
 *   })
 */
import { ref, onBeforeUnmount } from 'vue'

interface Options {
    lang?: string
    continuous?: boolean
    interimResults?: boolean
    onFinal?: (text: string) => void
    onInterim?: (text: string) => void
}

export function useSpeechRecognition(opts: Options = {}) {
    // 兼容标准与 webkit 前缀
    const Ctor: any =
        (window as any).SpeechRecognition ||
        (window as any).webkitSpeechRecognition

    const supported = !!Ctor
    const listening = ref(false)
    const interim = ref('')
    const error = ref<string>('')

    let rec: any = null

    function build() {
        if (!Ctor) return null
        const r = new Ctor()
        r.lang = opts.lang || 'zh-CN'
        r.continuous = opts.continuous !== false
        r.interimResults = opts.interimResults !== false

        r.onresult = (event: any) => {
            let finalText = ''
            let interimText = ''
            for (let i = event.resultIndex; i < event.results.length; i++) {
                const res = event.results[i]
                const t = res[0].transcript
                if (res.isFinal) finalText += t
                else interimText += t
            }
            if (interimText) {
                interim.value = interimText
                opts.onInterim?.(interimText)
            }
            if (finalText) {
                interim.value = ''
                opts.onFinal?.(finalText)
            }
        }
        r.onerror = (e: any) => {
            error.value = e?.error || '识别出错'
            listening.value = false
        }
        r.onend = () => {
            listening.value = false
            interim.value = ''
        }
        return r
    }

    function start() {
        if (!supported) {
            error.value = '当前浏览器不支持语音识别'
            return
        }
        if (listening.value) return
        error.value = ''
        rec = build()
        try {
            rec?.start()
            listening.value = true
        } catch (e: any) {
            error.value = e?.message || '启动失败'
            listening.value = false
        }
    }

    function stop() {
        if (!rec || !listening.value) return
        try {
            rec.stop()
        } catch {
            // ignore
        }
        listening.value = false
    }

    function toggle() {
        if (listening.value) stop()
        else start()
    }

    onBeforeUnmount(() => {
        stop()
        rec = null
    })

    return { supported, listening, interim, error, start, stop, toggle }
}
