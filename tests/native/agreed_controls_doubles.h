#pragma once
// Interface doubles for the agreed_controls fixture (wave C2): only what
// preferences/configobject.cpp includes besides Qt and the control framework.
#include <QDomNode>
#include <QString>

// util/cmdlineargs.h
class CmdlineArgs {
  public:
    static CmdlineArgs& Instance() {
        static CmdlineArgs args;
        return args;
    }
    QString getResourcePath() const {
        return QStringLiteral("/nonexistent-mixpi-resources/");
    }
};

// util/xml.h
class XmlParse {
  public:
    static QString selectNodeQString(const QDomNode&, const QString&) {
        return QString();
    }
};
