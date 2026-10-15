package com.melodia.app

import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import java.io.File
import java.io.FileOutputStream
import java.io.RandomAccessFile
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.channels.FileChannel

/** Converte un file audio (m4a/webm/opus...) in WAV PCM 16 bit, 44.1 kHz, stereo. Usato da Python (al posto di ffmpeg). */
object Wav {
    private const val OUT_RATE = 44100

    @JvmStatic
    fun convert(src: String, dst: String) {
        val tmp = File("$dst.pcm")
        val ex = MediaExtractor()
        ex.setDataSource(src)
        var idx = -1
        var fmt: MediaFormat? = null
        for (i in 0 until ex.trackCount) {
            val f = ex.getTrackFormat(i)
            if ((f.getString(MediaFormat.KEY_MIME) ?: "").startsWith("audio/")) { idx = i; fmt = f; break }
        }
        require(idx >= 0 && fmt != null) { "nessuna traccia audio" }
        ex.selectTrack(idx)
        val codec = MediaCodec.createDecoderByType(fmt.getString(MediaFormat.KEY_MIME)!!)
        codec.configure(fmt, null, null, 0)
        codec.start()
        var sr = fmt.getInteger(MediaFormat.KEY_SAMPLE_RATE)
        var ch = fmt.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
        val info = MediaCodec.BufferInfo()
        var inDone = false
        var outDone = false
        var total = 0L
        FileOutputStream(tmp).use { os ->
            val chunk = ByteArray(1 shl 16)
            while (!outDone) {
                if (!inDone) {
                    val ii = codec.dequeueInputBuffer(10000)
                    if (ii >= 0) {
                        val buf = codec.getInputBuffer(ii)!!
                        val n = ex.readSampleData(buf, 0)
                        if (n < 0) {
                            codec.queueInputBuffer(ii, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                            inDone = true
                        } else {
                            codec.queueInputBuffer(ii, 0, n, ex.sampleTime, 0)
                            ex.advance()
                        }
                    }
                }
                val oi = codec.dequeueOutputBuffer(info, 10000)
                when {
                    oi >= 0 -> {
                        val ob = codec.getOutputBuffer(oi)!!
                        ob.position(info.offset); ob.limit(info.offset + info.size)
                        var left = info.size
                        while (left > 0) {
                            val n = minOf(left, chunk.size)
                            ob.get(chunk, 0, n)
                            os.write(chunk, 0, n)
                            left -= n
                        }
                        total += info.size
                        codec.releaseOutputBuffer(oi, false)
                        if (info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) outDone = true
                    }
                    oi == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED -> {
                        val nf = codec.outputFormat
                        sr = nf.getInteger(MediaFormat.KEY_SAMPLE_RATE)
                        ch = nf.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
                    }
                }
            }
        }
        codec.stop(); codec.release(); ex.release()
        require(total > 0) { "decodifica vuota" }

        val inFrames = total / (2L * ch)
        val outFrames = inFrames * OUT_RATE / sr
        RandomAccessFile(tmp, "r").use { raf ->
            val map = raf.channel.map(FileChannel.MapMode.READ_ONLY, 0, total).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer()
            FileOutputStream(dst).use { out ->
                val dataLen = outFrames * 4
                val h = ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN)
                h.put("RIFF".toByteArray()); h.putInt((36 + dataLen).toInt()); h.put("WAVE".toByteArray())
                h.put("fmt ".toByteArray()); h.putInt(16); h.putShort(1); h.putShort(2)
                h.putInt(OUT_RATE); h.putInt(OUT_RATE * 4); h.putShort(4); h.putShort(16)
                h.put("data".toByteArray()); h.putInt(dataLen.toInt())
                out.write(h.array())
                val buf = ByteBuffer.allocate(1 shl 16).order(ByteOrder.LITTLE_ENDIAN)
                val ratio = sr.toDouble() / OUT_RATE
                var i = 0L
                fun sample(frame: Long, c: Int): Float {
                    val f = if (frame >= inFrames) inFrames - 1 else frame
                    val cc = if (ch == 1) 0 else minOf(c, ch - 1)
                    return map.get((f * ch + cc).toInt()).toFloat()
                }
                while (i < outFrames) {
                    buf.clear()
                    while (buf.remaining() >= 4 && i < outFrames) {
                        val pos = i * ratio
                        val i0 = pos.toLong()
                        val fr = (pos - i0).toFloat()
                        for (c in 0..1) {
                            val v = sample(i0, c) * (1 - fr) + sample(i0 + 1, c) * fr
                            buf.putShort(v.coerceIn(-32768f, 32767f).toInt().toShort())
                        }
                        i++
                    }
                    out.write(buf.array(), 0, buf.position())
                }
            }
        }
        tmp.delete()
    }
}
