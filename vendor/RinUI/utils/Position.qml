pragma Singleton
import QtQuick 2.15

QtObject {
    id: typography

    enum Type {
        Top,
        Bottom,
        Left,
        Right,
        TopLeft,
        TopRight,
        BottomLeft,
        BottomRight,
        Center,
        None
    }
}
