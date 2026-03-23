cask "prism-studio" do
  version "VERSION_PLACEHOLDER"
  
  sha256 arm: "SHA256_ARM64_PLACEHOLDER",
         intel: "SHA256_X86_64_PLACEHOLDER"

  url do |_params|
    if Hardware::CPU.arm?
      "https://github.com/MRI-Lab-Graz/prism-studio/releases/download/v#{version}/prism-studio-macOS-arm64.zip"
    else
      "https://github.com/MRI-Lab-Graz/prism-studio/releases/download/v#{version}/prism-studio-macOS-x86_64.zip"
    end
  end
  
  depends_on macos: ">= :big_sur"
  
  app "PrismStudio.app"
  
  postflight do
    system_command "/bin/bash", args: ["-c", "xattr -dr com.apple.quarantine \"#{staged_path}/PrismStudio.app\" 2>/dev/null || true"]
  end

  zap trash: [
    "~/Library/Preferences/prism-studio.plist",
    "~/Library/Application Support/prism-studio",
  ]

  homepage "https://github.com/MRI-Lab-Graz/prism-studio"
  
  description <<~EOS
    PRISM Studio: Hybrid dataset validation tool for psychological experiments.
    Enforces PRISM structure (BIDS-inspired) while remaining BIDS-compatible.
  EOS
  
  livecheck do
    url :homepage
    strategy :github_latest
  end
end
