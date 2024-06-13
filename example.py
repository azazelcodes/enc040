import enc040

if __name__ == "__main__":
    encoder = enc040(CLK=17, DT=18, SW=27)

    # Start the encoder in a separate thread
    import threading
    encoder_thread = threading.Thread(target=encoder.watch)
    encoder_thread.start()

    while True:
        if encoder.isClicked():
            print("Button was clicked")
        
        if encoder.isHeld():
            print("Button was held")

        encoder.waitForInc()
        print("Increment detected")

        encoder.waitForDec()
        print("Decrement detected")
