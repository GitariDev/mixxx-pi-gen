#include <cstdlib>
#include <iostream>
#include <sstream>
#include <stdexcept>

#include "sourceidentity.h"

using namespace mixxx::rekordbox;

void require(bool condition, const std::string& message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

int main(int argc, char** argv) {
    try {
        const SourceMount mount{"20", "8:33", "/", "/media/pi/Guest"};
        const PhysicalGeneration original{"boot", "mnt:[1]", "/sys/devices/usb/disk", "8:32", "50"};
        const auto importedRevision = databaseRevision(sourceRevision(mount, original), "4096:1000:0:20");
        require(!importedRevision.empty(), "initial import identity");
        require(sameSourceRevision(mount.path, importedRevision, mount.path, importedRevision), "unchanged cached import");
        auto replacement = original;
        replacement.diskseq = "51";
        const auto rediscoveredRevision = databaseRevision(sourceRevision(mount, replacement), "4096:1000:0:20");
        require(!sameSourceRevision(mount.path, importedRevision, mount.path, rediscoveredRevision),
                "replacement AFTER import must invalidate cached node with reused mount id and identical database metadata");
        require(sameSourceRevision(mount.path, rediscoveredRevision, mount.path, rediscoveredRevision), "replacement reimport reusable");
        replacement = original;
        replacement.nameSpace = "mnt:[2]";
        require(sourceRevision(mount, replacement) != sourceRevision(mount, original), "namespace provenance");
        replacement = original;
        replacement.boot = "other-boot";
        require(sourceRevision(mount, replacement) != sourceRevision(mount, original), "boot provenance");
        replacement = original;
        replacement.diskseq.clear();
        require(sourceRevision(mount, replacement).empty(), "missing generation fails closed");
        require(!sameSourceRevision(mount.path, "", mount.path, ""), "unknown revisions never reused");
        require(!resolvedOnMount(mount, "8:81", mount.id), "cross-device database");
        require(!resolvedOnMount(mount, mount.device, "21"), "same-device different mount id");
        require(!resolvedOnMount(mount, mount.device, ""), "unknown descriptor mount id");
        for (const auto& text : {"pos: 0\n", "mnt_id: 20\nmnt_id: 20\n", "mnt_id: invalid\n", "mnt_id: 0\n"}) {
            std::istringstream stream(text);
            require(descriptorMountId(stream).empty(), "fdinfo fail closed");
        }
        std::istringstream fdinfo("pos: 0\nmnt_id:\t20\n");
        require(descriptorMountId(fdinfo) == "20", "parse kernel fdinfo");
        std::istringstream covered(
                "1 0 179:2 / / rw - ext4 root rw\n"
                "20 1 8:33 / /media/pi/Guest rw - exfat selected rw\n"
                "21 1 8:81 / /media/pi rw - vfat covering rw\n");
        const auto hidden = containingMount(mount.path, covered);
        require(hidden.id == "20", "hidden descendant remains in mountinfo");
        require(!resolvedOnMount(hidden, "8:81", "21"), "covered ancestor must fail despite mountinfo membership");
        std::cout << "PASS native production identity: replacement AFTER import, generation/namespace/boot, cached reuse, covered ancestor, cross-device and same-device/different-mount, fdinfo fail-closed\n";
#ifdef __linux__
        if (argc != 2) {
            std::cout << "SKIP Linux kernel probes: supply a unique scratch directory on a block-backed filesystem\n";
            return 0;
        }
        const auto scratch = std::filesystem::path(argv[1]) / "identity-fixture";
        require(std::filesystem::create_directory(scratch), "fresh scratch fixture required");
        const auto sourcePath = scratch.string();
        auto observed = inspectSource(sourcePath);
        require(!observed.revision.empty() && observed.database.empty(), "real directory and physical generation");
        const auto expectedMount = observed.mount;
        const int retained = observed.directoryDescriptor->value;
        require(descriptorOnMount(retained, expectedMount, true), "retained descriptor valid");
        SourceMount hiddenMount = expectedMount;
        hiddenMount.id = "999999999";
        hiddenMount.path = sourcePath;
        require(!descriptorOnMount(retained, hiddenMount, true), "actual descriptor rejects synthetic covered mount");
        std::filesystem::create_directories(scratch / "PIONEER/rekordbox");
        const auto database = scratch / "PIONEER/rekordbox/export.pdb";
        std::ofstream(database) << "synthetic metadata fixture, not an actual export";
        auto withDatabase = inspectSource(sourcePath);
        require(!withDatabase.database.empty(), "database descriptor on selected mount");
        require(!descriptorOnMount(withDatabase.databaseDescriptor->value, hiddenMount, false),
                "actual database descriptor rejects same-device different mount id");
        auto imported = withDatabase.database;
        require(imported == inspectSource(sourcePath).database, "real unchanged source reuse");
        std::filesystem::remove(database);
        std::filesystem::create_symlink("/proc/version", database);
        require(inspectSource(sourcePath).revision.empty(), "cross-volume export.pdb symlink rejected");
        std::filesystem::remove(database);
        std::filesystem::remove_all(scratch / "PIONEER");
        std::filesystem::create_symlink("/proc", scratch / "PIONEER");
        require(descriptorOnMount(retained, expectedMount, true), "directory descriptor remains bound");
        SourceDescriptor proc(::open("/proc", O_PATH | O_DIRECTORY | O_CLOEXEC));
        SourceDescriptor procSys(::open("/proc/sys", O_PATH | O_DIRECTORY | O_CLOEXEC));
        std::ifstream mountInfo("/proc/self/mountinfo");
        const auto procMount = containingMount("/proc", mountInfo);
        std::ifstream mountInfoAgain("/proc/self/mountinfo");
        const auto sysMount = containingMount("/proc/sys", mountInfoAgain);
        require(descriptorOnMount(proc.value, procMount, true), "real proc descriptor");
        require(descriptorOnMount(procSys.value, sysMount, true), "real nested path descriptor");
        auto differentMount = sysMount;
        differentMount.id = "999999999";
        require(!descriptorOnMount(procSys.value, differentMount, true), "actual descriptor same-device different mount rejection");
        std::filesystem::remove_all(scratch);
        observed = {};
        require(::fcntl(retained, F_GETFD) == -1 && errno == EBADF, "RAII closes directory descriptor");
        std::cout << "PASS Linux actual O_PATH/fstat/fdinfo: directory and database, cross-volume symlink, same-device/different expected mount, covered-mount mismatch, descriptor close\n";
#else
        (void)argc;
        (void)argv;
        require(inspectSource("/").revision.empty(), "unsupported kernel fails closed");
        std::cout << "SKIP Linux kernel descriptor probes on this host; run the same executable on ARM Linux\n";
#endif
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
    return 0;
}
