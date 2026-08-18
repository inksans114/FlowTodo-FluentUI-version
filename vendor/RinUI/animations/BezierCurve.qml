pragma Singleton
import QtQuick 2.15

QtObject {
    property list<real> fastInvoke: [0 ,0 ,0 ,1 ,1 ,1]
    property list<real> strongInvoke: [0.13 ,1.62 ,0 ,0.92 ,1 ,1]
    property list<real> fastDismiss: [0 , 0 ,0 ,1 ,1 ,1]
    property list<real> softDismiss: [1 ,0 ,1 ,1 ,1, 1]
    property list<real> pointToPoint: [0.55,0.55,0 ,1 , 1, 1]
    property list<real> fadeIn: [0 ,0 ,1 ,1 ,1 ,1]
    property list<real> fadeOut: [0 ,0 ,1 ,1 ,1 ,1]
    property list<real> fade: [0 ,0 ,1 ,1 ,1 ,1]
}