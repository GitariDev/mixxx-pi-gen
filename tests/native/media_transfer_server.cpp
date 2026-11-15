#include "library/media/copyservice.h"
#include <atomic>
#include <chrono>
#include <fstream>
#include <iostream>
#include <thread>

int main(int argc, char** argv) {
#ifdef __linux__
    if (argc != 2) return 2;
    const std::string root = argv[1];
    mixxx::media::CopyService service(root + "/ipc", {root}, [&](const std::string& path) {
        const std::string label = path.find("/source") != std::string::npos ? "A" : "B";
        std::ifstream revision(root + "/revision");
        std::string version;
        revision >> version;
        return mixxx::media::Binding{label + version, label + "-source" + version, std::make_shared<int>(1)};
    });
    if (!service.ready()) return 3;
    service.tick();
    std::atomic<bool> stopping{false};
    std::thread worker([&] {
        while (!stopping) {
            service.tick();
            std::this_thread::sleep_for(std::chrono::milliseconds(2));
        }
    });
    std::map<std::string, mixxx::media::MediaUseRegistry::Drain> drains;
    std::cout << "READY" << std::endl;
    std::string command, generation;
    while (std::cin >> command >> generation) {
        if (command == "transfer") {
            std::string source;
            std::cin >> source;
            const auto snapshot = service.transferStatus({generation, source, {}});
            std::cout << snapshot.valid << ' ' << snapshot.progressValid << ' '
                      << static_cast<int>(snapshot.phase) << ' ' << static_cast<int>(snapshot.status)
                      << ' ' << snapshot.progress << ' ' << snapshot.activeJobs << std::endl;
            continue;
        }
        if (command == "drain") drains.emplace(generation, mixxx::media::registry().beginDrain(generation));
        if (command == "release") drains.erase(generation);
        std::cout << (drains.count(generation) && drains.at(generation).snapshot().locallyIdle() ? "IDLE" : "BUSY") << std::endl;
    }
    stopping = true;
    worker.join();
    return 0;
#else
    (void)argc;
    (void)argv;
    return 77;
#endif
}
