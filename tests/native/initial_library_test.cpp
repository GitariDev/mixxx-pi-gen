#include <QCoreApplication>
#include <QJsonDocument>
#include <QJsonObject>
#include <iostream>

#include "library/initiallibrary.h"

int main(int argc, char** argv) {
    QCoreApplication application(argc, argv);
    const auto arguments = application.arguments();
    if (arguments.size() != 5) {
        return 2;
    }
    int calls = 0;
    QString registered;
    const auto result = mixpi::initiallibrary::initialize(
            arguments.at(2) == QStringLiteral("1"),
            arguments.at(3) == QStringLiteral("1"),
            arguments.at(1),
            [&](const QString& directory) {
                ++calls;
                registered = directory;
                return arguments.at(4) == QStringLiteral("1");
            });
    const QJsonObject output{
            {QStringLiteral("result"), static_cast<int>(result)},
            {QStringLiteral("calls"), calls},
            {QStringLiteral("registered"), registered},
    };
    std::cout << QJsonDocument(output).toJson(QJsonDocument::Compact).constData() << '\n';
    return 0;
}
