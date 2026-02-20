from core.rt_audio_engine import RealTimeAudioEngine
from controllers.player_controller import PlayerController
from ui.main_window import MainWindow


def main():
    engine = RealTimeAudioEngine(blocksize=2048)
    controller = PlayerController(engine)
    app = MainWindow(controller)
    app.mainloop()


if __name__ == "__main__":
    main()