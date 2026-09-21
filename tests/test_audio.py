from audio.microphone import Microphone
from audio.speaker import Speaker
def main():
    microphone = Microphone()
    speaker = Speaker()
    speaker.start_stream()  
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
            audio = microphone.read()
            speaker.play(audio.tobytes())

    except KeyboardInterrupt:
        print()
        print("Stopping...")

    finally:
        microphone.stop_stream()
        speaker.stop_stream()
        
if __name__ == "__main__":
    main()