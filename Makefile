all:	lint

lint:
	-pylint --rcfile=pylintrc *.py

clean:
	-find . -type f -name "*~" -exec rm -f {} \;
	-rm -fr __pycache__

distclean:	clean

