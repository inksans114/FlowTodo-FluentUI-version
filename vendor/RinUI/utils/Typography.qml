pragma Singleton
import QtQuick 2.15

QtObject {
    id: typography

    enum Type {
        Display,
        TitleLarge,
        Title,
        Subtitle,
        Body,
        BodyStrong,
        BodyLarge,
        Caption
    }
}
