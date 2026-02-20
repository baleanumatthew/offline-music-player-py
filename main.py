from core.audio_engine import AudioEngine
from controllers.player_controller import PlayerController
from ui.main_window import MainWindow


def main():
    engine = AudioEngine()
    controller = PlayerController(engine)
    app = MainWindow(controller)
    app.mainloop()


if __name__ == "__main__":
    main()