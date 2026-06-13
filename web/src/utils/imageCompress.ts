/**
 * 浏览器侧图片压缩工具。
 *
 * - 长边超过 maxSide 等比缩放
 * - 输出统一为 JPEG（除非原图很小且小于 sizeLimitKB，那就保持原文件）
 * - 用 canvas 渲染，不依赖任何库
 */
export async function compressImage(
    file: File,
    opts: { maxSide?: number; quality?: number; sizeLimitKB?: number } = {}
): Promise<File> {
    const { maxSide = 1280, quality = 0.85, sizeLimitKB = 1024 } = opts

    // 已经是小图就不压
    if (file.size <= sizeLimitKB * 1024 && file.type.startsWith('image/jpeg')) {
        return file
    }

    const img = await loadImage(file)
    const ratio = Math.min(1, maxSide / Math.max(img.width, img.height))
    const w = Math.round(img.width * ratio)
    const h = Math.round(img.height * ratio)

    const canvas = document.createElement('canvas')
    canvas.width = w
    canvas.height = h
    const ctx = canvas.getContext('2d')!
    ctx.drawImage(img, 0, 0, w, h)

    const blob: Blob = await new Promise((resolve, reject) => {
        canvas.toBlob(
            (b) => (b ? resolve(b) : reject(new Error('canvas toBlob 失败'))),
            'image/jpeg',
            quality
        )
    })

    const newName = file.name.replace(/\.\w+$/, '') + '.jpg'
    return new File([blob], newName, { type: 'image/jpeg' })
}

function loadImage(file: File): Promise<HTMLImageElement> {
    return new Promise((resolve, reject) => {
        const url = URL.createObjectURL(file)
        const img = new Image()
        img.onload = () => {
            URL.revokeObjectURL(url)
            resolve(img)
        }
        img.onerror = (e) => {
            URL.revokeObjectURL(url)
            reject(e)
        }
        img.src = url
    })
}
