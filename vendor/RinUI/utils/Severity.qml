pragma Singleton
import QtQuick 2.15

QtObject {
    id: typography

    enum Type {
        Info,
        Success,
        Warning,
        Error
    }
}
