// BUG-107 / DEV-076: exercise the production fallback without SDK or Toolkit calls.
#include <stdexcept>
#include <string>
#include <iostream>

using J = int;
#include "surface_loft.cpp"

int main() {
    try {
        generic_surface_loft(0);
    } catch (const std::runtime_error &error) {
        std::string message(error.what());
        if (message.find("SURFACE_LOFT_SDK_UNAVAILABLE") == std::string::npos ||
            message.find("Probbl.h") == std::string::npos)
            return 2;
        std::cout << message << '\n';
        return 0;
    }
    return 1; // No missing-header branch may claim a feature succeeded.
}
