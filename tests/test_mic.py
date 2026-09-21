import numpy as np
from audio.microphone import Microphone


def calculate_rms(audio):
    audio = audio.astype(np.float64)
    return np.sqrt(np.mean(audio ** 2))


def calculate_peak(audio):
    return np.max(np.abs(audio))


def main():
    microphone = Microphone()

    try:
        microphone.find_device()
        microphone.start_stream()

        print()
        print("==============================")
        print(" AUDIO PIPELINE TEST")
        print("==============================")
        print()
        print("Input  : 48 kHz / 32-bit / stereo")
        print("Output : 16 kHz / 16-bit / mono")
        print()
        print("Nói vào microphone...")
        print("Ctrl+C để thoát.")
        print()

        while True:
            audio = microphone.read_debug()
            print(audio)
            # rms = calculate_rms(audio)
            # peak = calculate_peak(audio)

            # if rms > 0:
            #     dbfs = 20 * np.log10(rms / 32768)
            # else:
            #     dbfs = -100

            # print(
            #     f"Shape: {audio.shape} | "
            #     f"Dtype: {audio.dtype} | "
            #     f"RMS: {rms:8.1f} | "
            #     f"Peak: {peak:6d} | "
            #     f"dBFS: {dbfs:6.1f}"
            # )

    except KeyboardInterrupt:
        print()
        print("Stopping...")

    finally:
        microphone.stop_stream()


if __name__ == "__main__":
    main()

# import serial, time
# s = serial.Serial('/dev/ttyACM0', 115200); 
# time.sleep(2)
# s.write(b'STOP\n')
# print('Gửi lệnh thành công!')