Pod::Spec.new do |s|
  s.name           = 'LiveAudio'
  s.version        = '1.0.0'
  s.summary        = 'Echo-cancelled microphone and speech player for MemoryPal live Talk-back'
  s.description    = s.summary
  s.license        = 'MIT'
  s.author         = 'MemoryPal'
  s.homepage       = 'https://github.com/TKSMG/MemoryPal'
  s.platforms      = { :ios => '16.4' }
  s.swift_version  = '5.9'
  s.source         = { git: 'https://github.com/TKSMG/MemoryPal.git' }
  s.static_framework = true

  s.dependency 'ExpoModulesCore'

  s.source_files = "**/*.{h,m,swift}"
  s.pod_target_xcconfig = {
    'DEFINES_MODULE' => 'YES',
    'SWIFT_COMPILATION_MODE' => 'wholemodule'
  }
end
