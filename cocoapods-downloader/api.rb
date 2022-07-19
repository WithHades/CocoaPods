module Pod
  module Downloader
    # The Downloader::Hooks module allows to adapt the Downloader to
    # the UI of other gems.
    #
    module API
      # Executes
      # @return [String] the output of the command.
      #
      def execute_command(executable, command, raise_on_failure = false)
        require 'shellwords'
        command = command.map(&:to_s).map(&:shellescape).join(' ')
        =begin
        require 'open3'
        o, e, s = Open3.capture3(command, :stdin_data=>"244036962@qq.com\n#{ENV['GITTOKEN']}\n")
        Open3.popen3(command) do |stdin, stdout, stderr, status|
          stdin.write command
          sleep 2
          stdin.write "244036962@qq.com\n"
          stdin.write ENV['GITTOKEN'] + "\n"
          stdin.close
          output = stdout.read
          stdout.close
          if !status.value.success?
            output = stderr.read()
          end
        end
        IO.popen(command, "r+") do |io|
          sleep 2
          io.puts("244036962@qq.com\n")
          io.puts("#{ENV['GITTOKEN']}\n")
          output = io.gets
          puts answer2
        end

        output = `\n#{executable} #{command} 2>&1`
        check_exit_code!(executable, command, output) if raise_on_failure
        puts output
        output
      end

      # Checks if the just executed command completed successfully.
      #
      # @raise  If the command failed.
      #
      # @return [void]
      #
      def check_exit_code!(executable, command, output)
        if $?.exitstatus != 0
          raise DownloaderError, "Error on `#{executable} #{command}`.\n#{output}"
        end
      end

      # Indicates that an action will be performed. The action is passed as a
      # block.
      #
      # @param  [String] message
      #         The message associated with the action.
      #
      # @yield  The action, this block is always executed.
      #
      # @return [void]
      #
      def ui_action(message)
        puts message
        yield
      end

      # Indicates that a minor action will be performed. The action is passed as
      # a block.
      #
      # @param  [String] message
      #         The message associated with the action.
      #
      # @yield  The action, this block is always executed.
      #
      # @return [void]
      #
      def ui_sub_action(message)
        puts message
        yield
      end

      # Prints an UI message.
      #
      # @param  [String] message
      #         The message associated with the action.
      #
      # @return [void]
      #
      def ui_message(message)
        puts message
      end
    end
  end
end
