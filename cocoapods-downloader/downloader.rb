require './cocoapods-downloader'

target_path = './'
options = { :svn => 'svn://svn.woxiu.com/ios/iwanpa/Pods/CommonComponent'}
options = Pod::Downloader.preprocess_options(options)
downloader = Pod::Downloader.for_target(target_path, options)
downloader.download